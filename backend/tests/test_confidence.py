"""Regression checks for a heuristic, not empirical confidence calibration."""
import copy
import json
from pathlib import Path
from uuid import UUID, uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.models.verification import VerificationRun
from app.confidence.algorithm import TransparentConfidenceAlgorithm
from app.confidence.repository import JsonConfidenceRepository
from app.verification.repository import JsonVerificationRepository
from test_verification import verification, create_ranked
from test_ranking import ranking
from test_mapping import mapping
from test_retrieval import setup


@pytest.fixture
def confidence(verification):
    config, client, base, source = verification
    response = client.post(base+'/verifications', json={'ranking_run_id': source['id']})
    assert response.json()['status'] == 'completed'
    return config, client, base, response.json()


def score(client, base, source):
    response = client.post(base+'/confidence-runs', json={'verification_run_id': source['id']})
    assert response.status_code == 201, response.text
    assert response.json()['status'] == 'completed', response.text
    return response.json()


def test_api_arithmetic_history_restart(confidence):
    config, client, base, source = confidence
    run = score(client, base, source)
    result = run['results'][0]
    assert run['verification_snapshot'] == source
    assert len(run['verification_sha256']) == 64
    assert run['algorithm_version'] == 'evidence-confidence-v1'
    assert result['label'] == 'Evidence Confidence' and not result['calibrated']
    assert result['evidence_status'] == source['results'][0]['evidence_status']
    assert result['components']['mapping_resolution']['points'] == 20
    assert result['components']['retrieved_coverage']['points'] == 20
    assert result['components']['useful_amount']['points'] == pytest.approx(20/3)
    assert result['components']['agreement']['points'] == 20
    assert result['raw_score'] == pytest.approx(sum(c['points'] for c in result['components'].values()))
    assert result['evidence_confidence'] == 50
    assert all(value is None for value in result['unknown_signals'].values())
    restarted = TestClient(create_app(config))
    assert restarted.get(base+'/confidence-runs/'+run['id']).json() == run
    second = score(client, base, source)
    assert second['id'] != run['id'] and second['results'] == run['results']
    assert len(restarted.get(base+'/confidence-runs').json()) == 2
    repo = JsonConfidenceRepository(config.storage_root)
    with pytest.raises(ValueError):
        repo.save(repo.get(UUID(run['video_id']), UUID(run['id'])))


CASES = json.loads((Path(__file__).resolve().parents[2] / 'evaluation/confidence/cases.json').read_text())


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['id'])
def test_authored_policy_cases(ranking, case):
    _, client, base, _ = ranking
    ranked = create_ranked(ranking, tuple(case['labels']))
    verified = client.post(base+'/verifications',json={'ranking_run_id':ranked['id']}).json()
    result = score(client,base,verified)['results'][0]
    assert result['evidence_confidence'] == case['expected_score']
    assert result['raw_score'] == pytest.approx(case['raw_score'])
    assert result['components']['agreement']['value'] == case['agreement']


def test_duplicate_invariance_and_support_contradiction_symmetry(ranking):
    _, client, base, _ = ranking
    results = []
    for labels in [('SUPPORTS',), ('SUPPORTS',)*8, ('CONTRADICTS',)]:
        ranked = create_ranked(ranking, labels, duplicate=True)
        verified = client.post(base+'/verifications',json={'ranking_run_id':ranked['id']}).json()
        results.append(score(client,base,verified)['results'][0])
    for result in results[1:]:
        assert result['components'] == results[0]['components']
        assert result['evidence_confidence'] == results[0]['evidence_confidence']


@pytest.mark.parametrize('mutation', ['hash','id','video','ranking_id','status','quote','coverage','missing_result','policy','parameters'])
def test_tampered_verification_rejected(confidence, mutation):
    config, client, base, source = confidence
    changed = copy.deepcopy(source)
    if mutation == 'hash': changed['ranking_sha256'] = 'bad'
    if mutation == 'id': changed['id'] = str(uuid4())
    if mutation == 'video': changed['video_id'] = str(uuid4())
    if mutation == 'ranking_id': changed['request']['ranking_run_id'] = str(uuid4())
    if mutation == 'status': changed['results'][0]['evidence_status'] = 'Contradicted'
    if mutation == 'quote': changed['results'][0]['citations'][0]['quote'] = 'invented'
    if mutation == 'coverage': changed['results'][0]['coverage']['mapped_passages'] = 999
    if mutation == 'missing_result': changed['results'] = []
    if mutation == 'policy': changed['policy_version'] = 'future-v99'
    if mutation == 'parameters': changed['parameters']['majority_vote'] = True
    path = config.storage_root/source['video_id']/'verifications'/(source['id']+'.json')
    path.write_text(json.dumps(changed))
    response = client.post(base+'/confidence-runs',json={'verification_run_id':source['id']})
    assert response.status_code == 409
    assert response.json()['detail']['code'] == ('unsupported_verification_version'
        if mutation in ('policy','parameters') else 'invalid_source_lineage')


def test_request_validation_and_not_ready(confidence):
    config, client, base, source = confidence
    assert client.post(base+'/confidence-runs',json={}).status_code == 422
    assert client.post(base+'/confidence-runs',json={'verification_run_id':'bad'}).status_code == 422
    assert client.post(base+'/confidence-runs',json={'verification_run_id':source['id'],'score':100}).status_code == 422
    assert client.post(base+'/confidence-runs',json={'verification_run_id':str(uuid4())}).status_code == 404
    assert client.get(base+'/confidence-runs/'+str(uuid4())).status_code == 404
    assert client.get(f'/videos/{uuid4()}/confidence-runs').status_code == 404
    changed = VerificationRun.model_validate_json(json.dumps(source))
    changed.id, changed.status = uuid4(), 'failed'
    JsonVerificationRepository(config.storage_root).save(changed)
    assert client.post(base+'/confidence-runs',json={'verification_run_id':str(changed.id)}).status_code == 409


def test_incomplete_coverage_and_unknown_annotations(confidence):
    source = VerificationRun.model_validate_json(json.dumps(confidence[3]))
    algorithm = TransparentConfidenceAlgorithm()
    before = algorithm.evaluate(source)[0]
    # Algorithm-level controlled changes; API rejects these unless replayed upstream.
    passage = source.ranking_snapshot.results[0].ranked[0]
    passage.directness, passage.source_role = 'direct', 'primary'
    passage.assessment_origin = 'user_supplied_unverified'
    passage.publication_date = '2026-10-28'
    assert algorithm.evaluate(source) == [before]
    source.results[0].coverage.failed_fetch_count = 1
    assert algorithm.evaluate(source)[0].evidence_confidence <= 25
    source.results[0].coverage.failed_fetch_count = 0
    source.results[0].coverage.retrieved_passages = 2
    result = algorithm.evaluate(source)[0]
    assert result.components['retrieved_coverage'].points == 10
    assert result.raw_score == pytest.approx(before.raw_score-10)


def test_busy_and_failure(confidence):
    config, _, base, source = confidence
    entered, release = Event(), Event()
    class Blocking(TransparentConfidenceAlgorithm):
        def evaluate(self, source):
            entered.set(); assert release.wait(5)
            return super().evaluate(source)
    client = TestClient(create_app(config,confidence_algorithm=Blocking()))
    request = {'verification_run_id':source['id']}
    with ThreadPoolExecutor() as executor:
        future = executor.submit(client.post,base+'/confidence-runs',json=request)
        assert entered.wait(2)
        try:
            assert client.post(base+'/confidence-runs',json=request).status_code == 503
            assert client.get('/health').status_code == 200
        finally: release.set()
        assert future.result().json()['status'] == 'completed'
    assert client.post(base+'/confidence-runs',json=request).status_code == 201
    class Broken(TransparentConfidenceAlgorithm):
        def evaluate(self, source): raise RuntimeError('secret-token')
    client = TestClient(create_app(config,confidence_algorithm=Broken()))
    result = client.post(base+'/confidence-runs',json=request)
    assert result.json()['status'] == 'failed' and 'secret-token' not in result.text
    assert client.get(base+'/confidence-runs/'+result.json()['id']).json() == result.json()


def test_unselected_proposition_has_zero_score(confidence):
    source = VerificationRun.model_validate_json(json.dumps(confidence[3]))
    source.ranking_snapshot.results = []
    proposition = source.results[0]
    proposition.citations = []
    proposition.coverage.mapped_passages = 0
    proposition.coverage.selected_passages = 0
    proposition.coverage.retrieved_passages = 0
    result = TransparentConfidenceAlgorithm().evaluate(source)[0]
    assert result.evidence_confidence == 0 and result.raw_score == 0
