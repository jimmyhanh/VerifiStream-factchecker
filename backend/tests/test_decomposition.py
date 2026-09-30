from uuid import UUID, uuid4
from threading import Event
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.models.claim import ClaimCandidate, ClaimRun, ClaimProviderInfo
from app.models.transcript import TranscriptResult, Segment
from app.models.video import VideoRecord, VideoStatus
from app.models.proposition import ClausePlan, TextSpan, DecompositionPlan
from app.claims.service import transcript_hash
from app.claims.repository import JsonClaimRepository
from app.database.repository import JsonVideoRepository
from app.decomposition.provider import EnglishRuleDecompositionProvider
from app.decomposition.repository import JsonDecompositionRepository
from app.decomposition.service import render_plan, snapshot_hash
from app.shared.config import Settings


def source_run(text, video_id=None, split=None):
    texts = [text] if split is None else split
    snapshot = TranscriptResult(language='en',duration_seconds=len(texts)*4,
        segments=[Segment(id=i,start=i*4,end=(i+1)*4,text=s) for i,s in enumerate(texts)],
        provider='fixture',provider_version='1',model='fixture',model_revision='1',engine_version='1',parameters={})
    candidate = ClaimCandidate(id=uuid4(),quote=text,char_start=0,char_end=len(text),
        signals=['numerical'],segment_ids=list(range(len(texts))),start_seconds=0,
        end_seconds=len(texts)*4,reason='Fixture assertion',needs_context=False)
    return ClaimRun(id=uuid4(),video_id=video_id or uuid4(),transcript_run_id=uuid4(),
        status='completed',provider=ClaimProviderInfo(name='fixture',version='1',parameters={}),
        transcript_snapshot=snapshot,transcript_sha256=transcript_hash(snapshot),candidates=[candidate])


def decompose(text):
    source=source_run(text)
    candidate=source.candidates[0]
    return render_plan(candidate,EnglishRuleDecompositionProvider().decompose(candidate),source)


def test_policy_example_four_related_propositions():
    result=decompose('The policy reduced unemployment by approximately 20% and created 500,000 jobs.')
    assert result.status=='decomposed'
    assert [p.text for p in result.propositions]==[
        'Unemployment declined by approximately 20%.',
        'The policy reduced unemployment by approximately 20%.',
        '500,000 jobs were created.',
        'The policy created 500,000 jobs.']
    assert [p.kind for p in result.propositions]==['observed_outcome','causal']*2
    assert result.propositions[0].related_proposition_ids==[result.propositions[1].id]
    assert result.propositions[1].related_proposition_ids==[result.propositions[0].id]
    assert all(p.needs_context for p in result.propositions)


@pytest.mark.parametrize('text,expected',[
    ('The city opened 2 schools and closed 1 hospital.', ['The city opened 2 schools.','The city closed 1 hospital.']),
    ('The city opened 2 schools but the county closed 1 hospital.', ['The city opened 2 schools.','the county closed 1 hospital.']),
    ('The city opened 2 schools and the county opened 3 clinics and closed 1 hospital.', ['The city opened 2 schools.','the county opened 3 clinics.','the county closed 1 hospital.']),
    ('The city has at least 20 schools.', ['The city has at least 20 schools.']),
    ('Unemployment fell from 5% to 4%.', ['Unemployment fell from 5% to 4%.']),
    ('The policy did not create 500 jobs.', ['The policy did not create 500 jobs.']),
    ('The drug did not cause the rash.', ['The drug did not cause the rash.']),
    ('It caused the flood.', ['It caused the flood.']),
    ('The mayor said that the policy created approximately 500 jobs.', ['The mayor said that approximately 500 jobs were created.','The mayor said that the policy created approximately 500 jobs.']),
    ('In California in 2024, the city opened 2 schools and closed 1 hospital.', ['In California in 2024, the city opened 2 schools.','In California in 2024, the city closed 1 hospital.']),
    ('The policy increased inflation by 2 percentage points in 2024.', ['Inflation increased by 2 percentage points in 2024.','The policy increased inflation by 2 percentage points in 2024.']),
])
def test_meaning_preservation(text,expected):
    result=decompose(text)
    assert result.status!='needs_review',result.review_reason
    assert [p.text for p in result.propositions]==[s[0].upper()+s[1:] for s in expected]
    for proposition in result.propositions:
        for part in proposition.source_parts:
            assert text[part.char_start:part.char_end]==part.quote


@pytest.mark.parametrize('text',[
    'The policy did not reduce unemployment and create 500 jobs.',
    'The policy may have created 500 jobs.',
    'If the policy created 500 jobs, unemployment would fall.',
    'The city opened schools and hospitals.',
    'Alice and Bob opened 2 schools.',
    'The city opened 2 schools or 3 hospitals.',
    'The city opened 2 schools and closed 1 hospital in 2024.',
    'The policy created jobs because taxes fell.',
    'The policy created only 500 jobs.',
    'The mayor denied that the policy created 500 jobs.',
    'The mayor said the policy created 500 jobs.',
    'The city opened 2 schools, attracting 100 students.',
    'The city opened 2 schools. The county closed 1 hospital.',
    'The company has a plan that created 500 jobs.',
    'Unemployment 20%.',
    'The policy reduced unemployment by twenty percent.',
    'The policy created 500 permanent jobs.',
    'The city opened 2 schools and 3 hospitals respectively.',
    'The city opened 2 schools without raising taxes.',
])
def test_ambiguous_scope_abstains_without_assertions(text):
    result=decompose(text)
    assert result.status=='needs_review'
    assert result.review_reason and result.propositions==[]
    assert result.source_quote==text


def test_negated_cause_does_not_imply_observed_event():
    result=decompose('The policy did not create 500 jobs.')
    assert len(result.propositions)==1
    assert result.propositions[0].kind=='causal'
    assert result.propositions[0].transformation=='source_clause'


@pytest.fixture
def setup(tmp_path):
    config=Settings(storage_root=tmp_path)
    video=VideoRecord(id=uuid4(),status=VideoStatus.completed,original_filename='sample.mp4',
        size_bytes=1,sha256='a'*64,duration_seconds=8)
    JsonVideoRepository(tmp_path).save(video)
    source=source_run('The policy reduced unemployment by 20% and created 500,000 jobs.', video.id,
        ['The policy reduced unemployment by 20%', 'and created 500,000 jobs.'])
    JsonClaimRepository(tmp_path).save(source)
    return config,video,source


def client_for(setup,provider=None):
    return TestClient(create_app(setup[0],decomposition_provider=provider))


def test_api_lineage_persistence_history_and_latest(setup):
    config,video,source=setup
    url=f'/videos/{video.id}'
    client=client_for(setup)
    assert client.get(url+'/propositions').status_code==404
    response=client.post(url+'/decompositions',json={})
    assert response.status_code==201
    first=response.json()
    assert first['status']=='completed' and first['proposition_count']==4 and first['unresolved_count']==0
    assert first['claim_run_id']==str(source.id)
    assert first['transcript_run_id']==str(source.transcript_run_id)
    assert first['claim_snapshot_sha256']==snapshot_hash(source)
    second=client.post(url+'/decompositions',json={'claim_run_id':str(source.id),
        'candidate_ids':[str(source.candidates[0].id)]}).json()
    assert first['id']!=second['id']
    restarted=client_for(setup)
    assert restarted.get(url+'/decompositions/'+first['id']).json()==first
    assert restarted.get(url+'/propositions').json()==second
    assert len(restarted.get(url+'/decompositions').json())==2
    parts=first['results'][0]['propositions'][2]['source_parts']
    canonical=source.transcript_snapshot.text
    assert all(canonical[p['char_start']:p['char_end']]==p['quote'] for p in parts)
    assert first['results'][0]['propositions'][2]['segment_ids']==[0,1] # shared subject
    repo=JsonDecompositionRepository(config.storage_root)
    with pytest.raises(ValueError): repo.save(repo.get(video.id,UUID(first['id'])))


def test_run_completion_is_not_resolution(setup):
    config,video,_=setup
    source=source_run('The policy did not reduce unemployment and create 500 jobs.',video.id)
    JsonClaimRepository(config.storage_root).save(source)
    client=client_for(setup)
    response=client.post(f'/videos/{video.id}/decompositions',json={}).json()
    assert response['status']=='completed'
    assert response['unresolved_count']==1 and response['proposition_count']==0
    assert client.get(f'/videos/{video.id}/propositions').json()==response


def test_empty_claim_extraction(setup):
    config,video,_=setup
    source=source_run('Hello.',video.id);source.candidates=[]
    JsonClaimRepository(config.storage_root).save(source)
    run=client_for(setup).post(f'/videos/{video.id}/decompositions',json={}).json()
    assert run['status']=='completed' and run['results']==[]


@pytest.mark.parametrize('body',[{'candidate_ids':[]},{'claim_run_id':'wrong'},
    {'candidate_ids':[str(UUID(int=1)),str(UUID(int=1))]},{'confidence':.9}])
def test_invalid_request(setup,body):
    assert client_for(setup).post(f'/videos/{setup[1].id}/decompositions',json=body).status_code==422


def test_no_cross_video_or_run_access(setup):
    config,video,source=setup
    client=client_for(setup);url=f'/videos/{video.id}/decompositions'
    assert client.post(url,json={'claim_run_id':str(uuid4())}).status_code==404
    assert client.post(url,json={'candidate_ids':[str(uuid4())]}).status_code==404
    other=video.model_copy(update={'id':uuid4()});JsonVideoRepository(config.storage_root).save(other)
    assert client.post(f'/videos/{other.id}/decompositions',json={'claim_run_id':str(source.id)}).status_code==404
    assert client.post(f'/videos/{other.id}/decompositions',json={}).status_code==404
    for path in ['/decompositions','/propositions','/decompositions/'+str(uuid4())]:
        assert client.get('/videos/'+str(uuid4())+path).status_code==404
    assert client.post('/videos/'+str(uuid4())+'/decompositions',json={}).status_code==404
    assert client.get(url+'/'+str(uuid4())).status_code==404


def test_failed_source_rejected_latest_success_used(setup):
    config,video,source=setup
    failed=source.model_copy(deep=True,update={'id':uuid4(),'status':'failed'})
    # ensure temporal ordering differs from original
    from app.models.video import utc_now
    failed.created_at=utc_now()
    JsonClaimRepository(config.storage_root).save(failed)
    client=client_for(setup);url=f'/videos/{video.id}/decompositions'
    assert client.post(url,json={'claim_run_id':str(failed.id)}).status_code==409
    assert client.post(url,json={}).json()['claim_run_id']==str(source.id)


@pytest.mark.parametrize('mode',['out_of_range','drop_qualifier','illegal_effect','exception'])
def test_invalid_provider_and_failure_history(setup,mode):
    class Bad(EnglishRuleDecompositionProvider):
        def decompose(self,candidate):
            if mode=='exception': raise RuntimeError('private-secret')
            plan=super().decompose(candidate)
            if mode=='out_of_range': plan.clauses[0].predicate.end=99999
            if mode=='drop_qualifier': plan.clauses[0].predicate.end-=4
            if mode=='illegal_effect': plan.clauses[0].predicate.start+=8
            return plan
    url=f'/videos/{setup[1].id}'
    good=client_for(setup).post(url+'/decompositions',json={}).json()
    client=client_for(setup,Bad())
    response=client.post(url+'/decompositions',json={})
    run=response.json()
    assert run['status']=='failed' and run['results']==[]
    assert run['finished_at'] is not None and 'private-secret' not in response.text
    assert client.get(url+'/propositions').json()==good


def test_corrupt_source_hash_and_language(setup):
    config,video,source=setup
    source=source.model_copy(deep=True,update={'id':uuid4()})
    source.transcript_sha256='wrong'
    JsonClaimRepository(config.storage_root).save(source)
    client=client_for(setup);url=f'/videos/{video.id}/decompositions'
    assert client.post(url,json={'claim_run_id':str(source.id)}).status_code==409
    source=source.model_copy(deep=True,update={'id':uuid4()})
    source.transcript_snapshot.language='vi'
    source.transcript_sha256=transcript_hash(source.transcript_snapshot)
    JsonClaimRepository(config.storage_root).save(source)
    assert client.post(url,json={'claim_run_id':str(source.id)}).status_code==422


def test_input_size_limit_and_capacity_release(setup):
    config,video,_=setup;config.max_claim_transcript_chars=5
    client=client_for(setup);url=f'/videos/{video.id}/decompositions'
    assert client.post(url,json={}).status_code==413
    config.max_claim_transcript_chars=100000
    assert client.post(url,json={}).json()['status']=='completed'


def test_busy_and_health_responsive(setup):
    entered,release=Event(),Event()
    class Blocking(EnglishRuleDecompositionProvider):
        def decompose(self,candidate):
            entered.set();assert release.wait(5)
            return super().decompose(candidate)
    client=client_for(setup,Blocking());url=f'/videos/{setup[1].id}/decompositions'
    with ThreadPoolExecutor() as pool:
        first=pool.submit(client.post,url,json={})
        try:
            assert entered.wait(5)
            assert client.get('/health').status_code==200
            assert client.post(url,json={}).status_code==503
        finally: release.set()
        assert first.result().json()['status']=='completed'
    assert client.post(url,json={}).json()['status']=='completed'


def test_negated_nonpolicy_causation_kind():
    result=decompose('The drug did not cause the rash.')
    assert len(result.propositions)==1
    assert result.propositions[0].kind=='causal'
    assert result.propositions[0].transformation=='source_clause'


def test_provider_cannot_drop_negation():
    text='The policy did not create 500 jobs.'
    source=source_run(text)
    # The omitted 'did not' leaves uncovered lexical source content.
    plan=DecompositionPlan(clauses=[ClausePlan(subject=TextSpan(start=0,end=10),
        predicate=TextSpan(start=text.index('create'),end=len(text)-1))])
    with pytest.raises(ValueError,match='Uncovered'):
        render_plan(source.candidates[0],plan,source)


def test_selected_subset_and_candidate_limit(setup):
    config,video,original=setup
    source=original.model_copy(deep=True,update={'id':uuid4()})
    source.candidates=[source.candidates[0].model_copy(update={'id':uuid4()}) for _ in range(101)]
    JsonClaimRepository(config.storage_root).save(source)
    client=client_for(setup);url=f'/videos/{video.id}/decompositions'
    assert client.post(url,json={'claim_run_id':str(source.id)}).status_code==413
    chosen=source.candidates[50].id
    result=client.post(url,json={'claim_run_id':str(source.id),'candidate_ids':[str(chosen)]}).json()
    assert result['status']=='completed'
    assert result['selected_candidate_ids']==[str(chosen)]
    assert len(result['results'])==1


def test_evaluation_abstentions_remain_in_denominator(tmp_path):
    import json
    import importlib.util
    from pathlib import Path
    path=Path(__file__).resolve().parents[2]/'evaluation'/'decomposition'/'evaluate.py'
    spec=importlib.util.spec_from_file_location('atomic_evaluation',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    fixture=tmp_path/'evaluation.json'
    fixture.write_text(json.dumps({'version':'metric-test','cases':[
        {'id':'one','text':'The city opened 2 schools.','needs_review':False,
         'expected':[{'text':'The city opened 2 schools.','kind':'factual'}]},
        {'id':'two','text':'The company acquired 3 factories.','needs_review':False,
         'expected':[{'text':'The company acquired 3 factories.','kind':'factual'}]},
        {'id':'three','text':'The city opened schools or hospitals.','needs_review':True,'expected':[]}]}))
    report=module.evaluate(fixture)
    assert report['resolution_coverage']==1/3
    assert report['exact_success_over_resolvable']==.5
    assert report['proposition_precision']==1 and report['proposition_recall']==.5
    assert report['correct_abstentions']==1 and report['unsafe_resolutions']==0
