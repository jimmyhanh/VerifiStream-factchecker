from fastapi.testclient import TestClient
from app.main import create_app
from app.shared.config import Settings
from test_api import setup, FakeMedia


def test_library_pagination_persistence(setup):
    settings, client = setup
    assert client.get('/videos').json() == []
    records = [client.post('/videos', files={'file': (f'{n}.mp4', b'x', 'video/mp4')}).json() for n in range(3)]
    restarted = TestClient(create_app(settings))
    assert [r['id'] for r in restarted.get('/videos?limit=2').json()] == [r['id'] for r in records[::-1][:2]]
    assert restarted.get('/videos?limit=2&offset=2').json() == [records[0]]
    assert restarted.get('/videos?offset=99').json() == []
    for query in ('limit=0', 'limit=101', 'offset=-1'):
        assert client.get('/videos?'+query).status_code == 422


def test_public_config_does_not_expose_secrets(tmp_path):
    config = Settings(storage_root=tmp_path, openai_api_key='private-openai', brave_search_api_key='private-brave', max_video_bytes=1234, max_duration_seconds=60)
    client = TestClient(create_app(config))
    assert client.get('/configuration').json() == {'max_video_bytes':1234, 'max_duration_seconds':60}


def test_cors_preflight_and_error_responses(setup):
    _, client = setup
    headers = {'Origin':'http://localhost:3000','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'}
    response = client.options('/videos',headers=headers)
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == headers['Origin']
    assert 'access-control-allow-credentials' not in response.headers
    headers['Origin'] = 'https://untrusted.example'
    assert client.options('/videos',headers=headers).status_code == 400
    response = client.post('/videos',json={},headers={'Origin':'http://localhost:3000'})
    assert response.status_code == 415 and response.headers['access-control-allow-origin'] == 'http://localhost:3000'


def test_configurable_cors_origin(monkeypatch,tmp_path):
    monkeypatch.setenv('CORS_ORIGINS','http://localhost:3333, http://127.0.0.1:3333')
    config = Settings.from_env().model_copy(update={'storage_root':tmp_path})
    assert config.cors_origins == ['http://localhost:3333','http://127.0.0.1:3333']
    client=TestClient(create_app(config,media=FakeMedia()))
    assert client.get('/configuration',headers={'Origin':'http://localhost:3333'}).headers['access-control-allow-origin']=='http://localhost:3333'
