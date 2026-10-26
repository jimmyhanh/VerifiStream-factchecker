"""M7 contract tests plus deterministic grouping/ranking fixtures; no paid providers."""
import copy
import hashlib
import json
from uuid import UUID, uuid4
from threading import Event
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.models.mapping import MappingRun
from app.models.ranking import RankingRequest, OriginDeclaration
from app.ranking.algorithm import TransparentRankingAlgorithm, group_sources
from app.ranking.repository import JsonRankingRepository
from app.evidence.repository import JsonMappingRepository
from app.retrieval.service import digest
from test_mapping import mapping
from test_retrieval import setup


@pytest.fixture
def ranking(mapping):
    config, client, base, _, _, request = mapping
    source = client.post(base+'/evidence-mappings',json=request).json()
    assert source['status']=='completed'
    return config, client, base, source


def parsed(source):
    return MappingRun.model_validate_json(json.dumps(source))


def expand(source, labels=('SUPPORTS','CONTRADICTS','QUALIFIES','CONTEXT')):
    run=parsed(source)
    original_source=run.retrieval_snapshot.sources[0]
    original_passage=run.retrieval_snapshot.results[0].passages[0]
    original_mapping=run.results[0]
    run.id=uuid4()
    run.retrieval_snapshot.sources=[]
    run.retrieval_snapshot.results[0].passages=[]
    run.results=[]
    for n,label in enumerate(labels):
        src=original_source.model_copy(deep=True)
        src.id=uuid4()
        src.text += f' Unique supplementary source material number {n}.'
        src.text_sha256=hashlib.sha256(src.text.encode()).hexdigest()
        src.final_url=src.requested_url=f'https://source{n}.example/report'
        src.domain=f'source{n}.example'
        p=original_passage.model_copy(deep=True)
        p.id,p.source_id=uuid4(),src.id
        p.lexical_relevance=round(.9-n*.1,2)
        result=original_mapping.model_copy(deep=True)
        result.passage_id,result.source_id=p.id,src.id
        result.citation_url=src.final_url
        if label in ('needs_review','failed'):
            result.status=label
            result.quote_char_start=result.quote_char_end=None
            if label=='failed':
                result.decision=None
                result.error_code='fixture_error'
            else:
                result.decision.status='needs_review'
                result.decision.relationship=None
                result.decision.evidence_quote=None
        else: result.decision.relationship=label
        run.results.append(result)
        run.retrieval_snapshot.sources.append(src)
        run.retrieval_snapshot.results[0].passages.append(p)
    run.request.passage_ids=[r.passage_id for r in run.results]
    run.status='partial' if 'failed' in labels else 'completed'
    run.retrieval_sha256=digest(run.retrieval_snapshot)
    return run


def test_api_snapshots_restart_and_immutable_history(ranking):
    config,client,base,source=ranking
    request={'mapping_run_id':source['id']}
    response=client.post(base+'/evidence-rankings',json=request)
    assert response.status_code==201
    run=response.json()
    assert run['status']=='completed' and run['mapping_snapshot']==source
    assert len(run['mapping_sha256'])==64
    result=run['results'][0]
    assert result['ranked'][0]['rank']==1
    assert result['ranked'][0]['directness']=='unknown'
    assert result['ranked'][0]['source_role']=='unknown'
    assert result['independence']=='unknown' and run['groups'][0]['independence']=='unknown'
    restarted=TestClient(create_app(config))
    assert restarted.get(base+'/evidence-rankings/'+run['id']).json()==run
    second=client.post(base+'/evidence-rankings',json=request).json()
    assert second['id']!=run['id']
    assert second['groups']==run['groups'] and second['results']==run['results']
    assert len(restarted.get(base+'/evidence-rankings').json())==2
    repository=JsonRankingRepository(config.storage_root)
    with pytest.raises(ValueError):repository.save(repository.get(UUID(run['video_id']),UUID(run['id'])))


def test_equal_stance_priority_stable_order_and_unranked(ranking):
    run=expand(ranking[3],('SUPPORTS','CONTRADICTS','QUALIFIES','CONTEXT','IRRELEVANT','needs_review','failed'))
    algorithm=TransparentRankingAlgorithm()
    request=RankingRequest(mapping_run_id=run.id)
    groups,results=algorithm.analyze(run,request)
    assert [p.relationship for p in results[0].ranked]==['SUPPORTS','CONTRADICTS','QUALIFIES','CONTEXT']
    assert {r.reason for r in results[0].unranked}=={'irrelevant','needs_review','failed'}
    first_order=[p.passage_id for p in results[0].ranked]
    run.results[0].decision.relationship='CONTRADICTS'
    run.results[1].decision.relationship='SUPPORTS'
    run.results.reverse();run.retrieval_snapshot.sources.reverse()
    new_groups,new_results=algorithm.analyze(run,request)
    assert [p.passage_id for p in new_results[0].ranked]==first_order
    assert new_groups==groups


def test_duplicates_diversified_without_dropping_contradiction(ranking):
    run=expand(ranking[3],('SUPPORTS','CONTRADICTS','QUALIFIES'))
    sources=run.retrieval_snapshot.sources
    sources[1].text=sources[0].text
    sources[1].text_sha256=sources[0].text_sha256
    groups,results=TransparentRankingAlgorithm().analyze(run,RankingRequest(mapping_run_id=run.id))
    assert len(groups)==2
    ranked=results[0].ranked
    assert [p.relationship for p in ranked]==['SUPPORTS','QUALIFIES','CONTRADICTS']
    assert ranked[-1].group_repeat is True
    assert results[0].useful_source_count==3 and results[0].useful_dependence_group_count==2
    assert results[0].independence=='unknown'


def test_exact_url_and_transitive_common_origin(ranking):
    run=expand(ranking[3],('SUPPORTS','CONTRADICTS','QUALIFIES'))
    a,b,c=run.retrieval_snapshot.sources
    b.final_url=a.final_url+'#section'
    quote=c.text[:20]
    request=RankingRequest(mapping_run_id=run.id,origins={c.id:OriginDeclaration(
        char_start=0,char_end=len(quote),quote=quote,rationale='Synthetic declaration',origin_url=b.final_url)})
    groups=group_sources([c,b,a],request)
    assert len(groups)==1 and len(groups[0].source_ids)==3
    assert {l.reason for l in groups[0].links}=={'same_final_url','shared_declared_origin'}
    assert any(l.provenance=='user_supplied_unverified' for l in groups[0].links)


def test_near_duplicate_threshold_and_boilerplate(ranking):
    run=expand(ranking[3],('SUPPORTS','CONTRADICTS'))
    a,b=run.retrieval_snapshot.sources
    original=' '.join(f'word{i}' for i in range(200))
    a.text=original
    b.text=original+' Additional syndicated closing note.'
    request=RankingRequest(mapping_run_id=run.id)
    groups=group_sources([a,b],request)
    assert len(groups)==1 and groups[0].links[0].reason=='near_duplicate_text'
    assert groups[0].links[0].similarity>=.9
    b.text=' '.join(f'other{i}' for i in range(200))+' '+original[:50]
    assert len(group_sources([a,b],request))==2
    a.text='cookie privacy policy '*100
    b.text='cookie privacy policy '*101
    assert len(group_sources([a,b],request))==2  # unique-shingle minimum
    a.text='Short school report.';b.text='Short school report updated.'
    assert len(group_sources([a,b],request))==2


def test_same_publisher_and_domain_do_not_establish_independence(ranking):
    run=expand(ranking[3],('SUPPORTS','CONTRADICTS'))
    a,b=run.retrieval_snapshot.sources
    a.publisher=b.publisher='Example Publisher'
    a.final_url='https://example.org/one';b.final_url='https://example.org/two'
    groups=group_sources([a,b],RankingRequest(mapping_run_id=run.id))
    assert len(groups)==2 and all(g.independence=='unknown' for g in groups)


def test_assessment_provenance_and_invalid_quote(ranking):
    config,client,base,source=ranking
    run=expand(source,('SUPPORTS','CONTRADICTS'))
    JsonMappingRepository(config.storage_root).save(run)
    p=run.retrieval_snapshot.results[0].passages[1]
    annotation={'char_start':p.char_start,'char_end':p.char_end,'quote':p.text,
                'rationale':'Reviewer identifies direct primary reporting in the quoted passage.',
                'directness':'direct','source_role':'primary'}
    request={'mapping_run_id':str(run.id),'assessments':{str(p.id):annotation}}
    response=client.post(base+'/evidence-rankings',json=request)
    assert response.status_code==201, response.text
    result=response.json()['results'][0]['ranked'][0]
    assert result['passage_id']==str(p.id) and result['assessment_origin']=='user_supplied_unverified'
    assert response.json()['request']==request | {'origins':{}}
    assert run.results[1].decision.relationship=='CONTRADICTS'
    annotation['quote']='invented'
    assert client.post(base+'/evidence-rankings',json=request).status_code==422


def test_origin_validation_and_caller_declared_group(ranking):
    config,client,base,source=ranking
    run=expand(source,('SUPPORTS','CONTRADICTS'))
    JsonMappingRepository(config.storage_root).save(run)
    origins={str(s.id):{'char_start':0,'char_end':10,'quote':s.text[:10],
        'rationale':'Synthetic user annotation; not validated origin semantics.',
        'origin_url':'https://original.example/report'} for s in run.retrieval_snapshot.sources}
    request={'mapping_run_id':str(run.id),'origins':origins}
    response=client.post(base+'/evidence-rankings',json=request)
    assert response.status_code==201 and len(response.json()['groups'])==1
    assert response.json()['groups'][0]['links'][0]['provenance']=='user_supplied_unverified'
    list(origins.values())[0]['origin_url']='http://127.0.0.1/secret'
    assert client.post(base+'/evidence-rankings',json=request).status_code==422


@pytest.mark.parametrize('mutation',['hash','quote','citation','proposition','duplicate','status'])
def test_tampered_mapping_rejected(ranking,mutation):
    config,client,base,source=ranking
    changed=copy.deepcopy(source)
    if mutation=='hash':changed['retrieval_sha256']='bad'
    if mutation=='quote':changed['results'][0]['quote_char_start']+=1
    if mutation=='citation':changed['results'][0]['citation_url']='https://invented.example/'
    if mutation=='proposition':changed['results'][0]['proposition_id']=str(uuid4())
    if mutation=='duplicate':changed['results']*=2
    if mutation=='status':changed['results'][0]['status']='needs_review'
    path=config.storage_root/source['video_id']/'evidence-mappings'/(source['id']+'.json')
    path.write_text(json.dumps(changed))
    assert client.post(base+'/evidence-rankings',json={'mapping_run_id':source['id']}).status_code==409


def test_partial_mapping_and_no_useful_evidence(ranking):
    config,client,base,source=ranking
    run=expand(source,('IRRELEVANT','needs_review','failed'))
    JsonMappingRepository(config.storage_root).save(run)
    response=client.post(base+'/evidence-rankings',json={'mapping_run_id':str(run.id)})
    assert response.status_code==201,response.text
    result=response.json()['results'][0]
    assert result['ranked']==[] and len(result['unranked'])==3
    assert result['useful_dependence_group_count']==0
    assert response.json()['status']=='completed'  # orchestration, not evidence sufficiency


def test_unknown_ids_and_schema(ranking):
    _,client,base,source=ranking
    assert client.post(base+'/evidence-rankings',json={'mapping_run_id':str(uuid4())}).status_code==404
    assert client.get(base+'/evidence-rankings/'+str(uuid4())).status_code==404
    assert client.get(f'/videos/{uuid4()}/evidence-rankings').status_code==404
    assert client.post(base+'/evidence-rankings',json={'mapping_run_id':'bad'}).status_code==422
    assert client.post(base+'/evidence-rankings',json={'mapping_run_id':source['id'],'bias_score':1}).status_code==422


def test_busy_health_release_and_failure_sanitization(ranking):
    config,_,base,source=ranking
    entered,release=Event(),Event()
    class Blocking(TransparentRankingAlgorithm):
        def analyze(self,*args):
            entered.set();assert release.wait(5)
            return super().analyze(*args)
    client=TestClient(create_app(config,ranking_algorithm=Blocking()))
    request={'mapping_run_id':source['id']}
    with ThreadPoolExecutor() as executor:
        future=executor.submit(client.post,base+'/evidence-rankings',json=request)
        assert entered.wait(2)
        try:
            assert client.post(base+'/evidence-rankings',json=request).status_code==503
            assert client.get('/health').status_code==200
        finally:release.set()
        assert future.result().json()['status']=='completed'
    class Broken(TransparentRankingAlgorithm):
        def analyze(self,*args):raise RuntimeError('private-secret')
    response=TestClient(create_app(config,ranking_algorithm=Broken())).post(base+'/evidence-rankings',json=request)
    assert response.json()['status']=='failed' and 'private-secret' not in response.text
