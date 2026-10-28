"""Status-policy tests are not a benchmark of factual/model accuracy."""
import copy
import json
from uuid import UUID, uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.models.mapping import MappingRun
from app.models.ranking import RankingRun, RankingRequest
from app.models.retrieval import PropositionRetrieval
from app.evidence.repository import JsonMappingRepository
from app.ranking.repository import JsonRankingRepository
from app.retrieval.service import digest
from app.verification.policy import SelectedEvidencePolicy, decide
from app.verification.repository import JsonVerificationRepository
from test_ranking import ranking, expand
from test_mapping import mapping
from test_retrieval import setup


@pytest.fixture
def verification(ranking):
    config,client,base,source=ranking
    ranked=client.post(base+'/evidence-rankings',json={'mapping_run_id':source['id']}).json()
    assert ranked['status']=='completed'
    return config,client,base,ranked


@pytest.mark.parametrize('labels,unresolved,expected',[
    (set(),False,'Insufficient Evidence'),
    ({'CONTEXT','IRRELEVANT'},False,'Insufficient Evidence'),
    ({'SUPPORTS'},False,'Supported'),
    ({'CONTRADICTS'},False,'Contradicted'),
    ({'QUALIFIES'},False,'Partially Supported'),
    ({'SUPPORTS','QUALIFIES'},False,'Partially Supported'),
    ({'SUPPORTS','CONTRADICTS'},False,'Conflicting Evidence'),
    ({'QUALIFIES','CONTRADICTS'},False,'Conflicting Evidence'),
    ({'SUPPORTS'},True,'Insufficient Evidence'),
    ({'CONTRADICTS'},True,'Insufficient Evidence'),
    ({'QUALIFIES'},True,'Insufficient Evidence'),
    ({'SUPPORTS','CONTRADICTS'},True,'Conflicting Evidence'),
])
def test_policy_table(labels,unresolved,expected):
    status,rule,explanation=decide(labels,unresolved)
    assert status==expected and rule and explanation


def test_api_citations_immutable_runs_and_restart(verification):
    config,client,base,ranking=verification
    request={'ranking_run_id':ranking['id']}
    response=client.post(base+'/verifications',json=request)
    assert response.status_code==201,response.text
    run=response.json()
    assert run['status']=='completed' and run['ranking_snapshot']==ranking
    assert run['policy_version']=='selected-evidence-v1' and len(run['ranking_sha256'])==64
    result=run['results'][0]
    assert result['evidence_status']=='Supported' and result['scope']=='selected_retrieved_evidence'
    citation=result['citations'][0]
    source=ranking['mapping_snapshot']['retrieval_snapshot']['sources'][0]
    assert source['text'][citation['char_start']:citation['char_end']]==citation['quote']
    assert citation['url']==source['final_url'] and citation['publication_date']==source['publication_date']
    assert result['independence']=='unknown'
    assert 'confidence' not in result
    restarted=TestClient(create_app(config))
    assert restarted.get(base+'/verifications/'+run['id']).json()==run
    second=client.post(base+'/verifications',json=request).json()
    assert second['id']!=run['id'] and second['results']==run['results']
    assert len(restarted.get(base+'/verifications').json())==2
    repo=JsonVerificationRepository(config.storage_root)
    with pytest.raises(ValueError):repo.save(repo.get(UUID(run['video_id']),UUID(run['id'])))


def create_ranked(ranking,labels,duplicate=False):
    config,client,base,source=ranking
    mapped=expand(source,labels)
    if duplicate:
        original=mapped.retrieval_snapshot.sources[0]
        for src in mapped.retrieval_snapshot.sources[1:]:
            src.text,src.text_sha256=original.text,original.text_sha256
        mapped.retrieval_sha256=digest(mapped.retrieval_snapshot)
    JsonMappingRepository(config.storage_root).save(mapped)
    ranked=client.post(base+'/evidence-rankings',json={'mapping_run_id':str(mapped.id)})
    assert ranked.status_code==201,ranked.text
    return ranked.json()


@pytest.mark.parametrize('labels,expected',[
    (('SUPPORTS',),'Supported'),
    (('CONTRADICTS',),'Contradicted'),
    (('QUALIFIES',),'Partially Supported'),
    (('SUPPORTS','QUALIFIES'),'Partially Supported'),
    (('SUPPORTS','CONTRADICTS'),'Conflicting Evidence'),
    (('CONTEXT','IRRELEVANT'),'Insufficient Evidence'),
    (('SUPPORTS','failed'),'Insufficient Evidence'),
    (('SUPPORTS','needs_review'),'Insufficient Evidence'),
    (('SUPPORTS','CONTRADICTS','failed'),'Conflicting Evidence'),
])
def test_api_status_matrix(ranking,labels,expected):
    ranked=create_ranked(ranking,labels)
    response=ranking[1].post(ranking[2]+'/verifications',json={'ranking_run_id':ranked['id']})
    assert response.status_code==201,response.text
    result=response.json()['results'][0]
    assert result['evidence_status']==expected
    assert result['coverage']['selected_passages']==len(labels)
    assert len(result['citations'])==sum(label not in ('failed','needs_review') for label in labels)


def test_repetition_cannot_outvote_contradiction_even_in_same_group(ranking):
    ranked=create_ranked(ranking,('SUPPORTS',)*8+('CONTRADICTS',),duplicate=True)
    result=ranking[1].post(ranking[2]+'/verifications',json={'ranking_run_id':ranked['id']}).json()['results'][0]
    assert result['evidence_status']=='Conflicting Evidence'
    assert result['decisive_dependence_group_count']==1
    assert len(result['citations'])==9
    assert list(result['group_relationships'].values())==[['CONTRADICTS','SUPPORTS']]


def test_unmapped_passages_and_unselected_propositions_are_explicit(ranking):
    config,client,base,source=ranking
    mapped=expand(source,('SUPPORTS','CONTRADICTS'))
    # Select only first passage; second stays in M5 retrieval scope, outside M6 selection.
    mapped.results=mapped.results[:1]
    mapped.request.passage_ids=[mapped.results[0].passage_id]
    retrieval=mapped.retrieval_snapshot
    p=retrieval.decomposition_snapshot.results[0].propositions[0].model_copy(deep=True)
    p.id=uuid4()
    retrieval.decomposition_snapshot.results[0].propositions.append(p)
    retrieval.decomposition_sha256=digest(retrieval.decomposition_snapshot)
    retrieval.request.proposition_ids.append(p.id)
    retrieval.results.append(PropositionRetrieval(proposition_id=p.id,query=p.text,status='no_passages'))
    mapped.retrieval_sha256=digest(retrieval)
    JsonMappingRepository(config.storage_root).save(mapped)
    ranked=client.post(base+'/evidence-rankings',json={'mapping_run_id':str(mapped.id)}).json()
    run=client.post(base+'/verifications',json={'ranking_run_id':ranked['id']}).json()
    results={r['proposition_id']:r for r in run['results']}
    assert results[str(p.id)]['evidence_status']=='Insufficient Evidence'
    assert results[str(p.id)]['citations']==[]
    first=results[str(mapped.results[0].proposition_id)]
    assert first['coverage']['retrieved_passages']==2 and first['coverage']['selected_passages']==1
    assert len(first['coverage']['unmapped_passage_ids'])==1
    assert first['evidence_status']=='Supported'  # explicitly selected scope, not complete evidence
    assert any('outside' in s for s in first['limitations'])


@pytest.mark.parametrize('mutation',['hash','quote','label','group','ranking','id','mapping_id','parameters','version'])
def test_tampered_or_unknown_ranking_rejected(verification,mutation):
    config,client,base,source=verification
    changed=copy.deepcopy(source)
    if mutation=='hash':changed['mapping_sha256']='bad'
    if mutation=='quote':changed['mapping_snapshot']['results'][0]['decision']['evidence_quote']='invented'
    if mutation=='label':changed['results'][0]['ranked'][0]['relationship']='CONTRADICTS'
    if mutation=='group':changed['groups'][0]['source_ids']=[]
    if mutation=='ranking':changed['results'][0]['ranked'][0]['rank']=999
    if mutation=='id':changed['id']=str(uuid4())
    if mutation=='mapping_id':changed['request']['mapping_run_id']=str(uuid4())
    if mutation=='parameters':changed['parameters']['jaccard_threshold']=.1
    if mutation=='version':changed['ranking_version']='unknown-v9'
    path=config.storage_root/source['video_id']/'evidence-rankings'/(source['id']+'.json')
    path.write_text(json.dumps(changed))
    response=client.post(base+'/verifications',json={'ranking_run_id':source['id']})
    assert response.status_code==409
    assert response.json()['detail']['code']==('unsupported_ranking_version' if mutation in ('parameters','version') else 'invalid_source_lineage')


def test_unknown_request_and_failed_ranking(verification):
    config,client,base,source=verification
    assert client.post(base+'/verifications',json={'ranking_run_id':str(uuid4())}).status_code==404
    assert client.get(base+'/verifications/'+str(uuid4())).status_code==404
    assert client.get(f'/videos/{uuid4()}/verifications').status_code==404
    assert client.post(base+'/verifications',json={}).status_code==422
    assert client.post(base+'/verifications',json={'ranking_run_id':source['id'],'verdict':'Supported'}).status_code==422
    changed=RankingRun.model_validate_json(json.dumps(source));changed.id=uuid4();changed.status='failed'
    JsonRankingRepository(config.storage_root).save(changed)
    assert client.post(base+'/verifications',json={'ranking_run_id':str(changed.id)}).status_code==409


def test_busy_release_and_sanitized_failure(verification):
    config,_,base,source=verification
    entered,release=Event(),Event()
    class Blocking(SelectedEvidencePolicy):
        def evaluate(self,ranking):
            entered.set();assert release.wait(5)
            return super().evaluate(ranking)
    client=TestClient(create_app(config,verification_policy=Blocking()))
    request={'ranking_run_id':source['id']}
    with ThreadPoolExecutor() as executor:
        future=executor.submit(client.post,base+'/verifications',json=request)
        assert entered.wait(2)
        try:
            assert client.post(base+'/verifications',json=request).status_code==503
            assert client.get('/health').status_code==200
        finally:release.set()
        assert future.result().json()['status']=='completed'
    assert client.post(base+'/verifications',json=request).status_code==201
    class Broken(SelectedEvidencePolicy):
        def evaluate(self,ranking):raise RuntimeError('secret-private-content')
    response=TestClient(create_app(config,verification_policy=Broken())).post(base+'/verifications',json=request)
    assert response.json()['status']=='failed' and 'secret-private-content' not in response.text
