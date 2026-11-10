import json
import subprocess
import wave
from pathlib import Path
from uuid import UUID, uuid4
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.main import create_app
from app.models.transcript import Segment, TranscriptResult
from app.models.video import VideoRecord, VideoStatus
from app.database.repository import JsonVideoRepository
from app.transcription.repository import JsonTranscriptRepository
from app.transcription.provider import FasterWhisperProvider
from app.shared.config import Settings
from app.shared.errors import ServiceError


def result(segments=None):
    return TranscriptResult(language='en', duration_seconds=1,
        segments=segments if segments is not None else [Segment(id=0, start=0, end=1, text='Hello world.')],
        provider='fake', provider_version='test', model='test', model_revision='abc',
        engine_version='test', parameters={})


class FakeProvider:
    def transcribe(self, audio, language):
        return result()


@pytest.fixture
def setup(tmp_path):
    settings = Settings(storage_root=tmp_path)
    video = VideoRecord(id=uuid4(), status=VideoStatus.completed, original_filename='test.mp4',
                        size_bytes=1, sha256='test', duration_seconds=1)
    repository = JsonVideoRepository(tmp_path)
    repository.save(video)
    audio = tmp_path / str(video.id) / 'audio.wav'
    with wave.open(str(audio), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b'\x00\x00' * 16000)
    return settings, video, repository


def client_for(setup, provider=None):
    return TestClient(create_app(setup[0], transcription_provider=provider or FakeProvider()))


def test_transcript_persistence_and_history(setup):
    client = client_for(setup)
    url = f'/videos/{setup[1].id}'
    assert client.get(url + '/transcript').status_code == 404
    one = client.post(url + '/transcriptions', json={})
    assert one.status_code == 201
    record = one.json()
    assert record['status'] == 'completed'
    assert record['text'] == 'Hello world.'
    assert len(record['audio_sha256']) == 64
    assert record['result']['segments'][0]['start'] == 0
    two = client.post(url + '/transcriptions', json={'language': 'en'}).json()
    assert record['id'] != two['id']
    assert client.get(url + '/transcript').json() == two
    restarted = client_for(setup)
    assert restarted.get(url + '/transcriptions/' + record['id']).json() == record
    assert len(restarted.get(url + '/transcriptions').json()) == 2
    saved = JsonTranscriptRepository(setup[0].storage_root)
    with pytest.raises(ValueError):
        saved.save(saved.get(setup[1].id, UUID(record['id'])))


@pytest.mark.parametrize('path', ['/transcript', '/transcriptions', '/transcriptions/' + str(uuid4())])
def test_unknown_video(setup, path):
    assert client_for(setup).get('/videos/' + str(uuid4()) + path).status_code == 404


def test_missing_audio_and_not_ready(setup):
    settings, video, repo = setup
    client = client_for(setup)
    url = f'/videos/{video.id}/transcriptions'
    video.status = VideoStatus.failed
    repo.save(video)
    assert client.post(url, json={}).status_code == 409
    video.status = VideoStatus.completed
    repo.save(video)
    (settings.storage_root / str(video.id) / 'audio.wav').unlink()
    assert client.post(url, json={}).status_code == 409


def test_failed_run_preserves_success(setup):
    class Failing:
        def transcribe(self, audio, language):
            raise ServiceError('transcription_timeout', 'Timed out.', 504)
    url = f'/videos/{setup[1].id}'
    success = client_for(setup).post(url + '/transcriptions', json={}).json()
    client = client_for(setup, Failing())
    failure = client.post(url + '/transcriptions', json={}).json()
    assert failure['status'] == 'failed'
    assert failure['error_code'] == 'transcription_timeout'
    assert failure['finished_at'] is not None
    assert client.get(url + '/transcript').json() == success
    assert len(client.get(url + '/transcriptions').json()) == 2


def test_silence_is_empty_success(setup):
    class Silent:
        def transcribe(self, audio, language):
            return result([])
    record = client_for(setup, Silent()).post(f'/videos/{setup[1].id}/transcriptions', json={}).json()
    assert record['status'] == 'completed'
    assert record['text'] == ''
    assert record['result']['segments'] == []


@pytest.mark.parametrize('body', [{'language': 'EN'}, {'language': '../en'}, {'model': 'invalid'}])
def test_request_validation(setup, body):
    assert client_for(setup).post(f'/videos/{setup[1].id}/transcriptions', json=body).status_code == 422


@pytest.mark.parametrize('start,end', [(2, 1), (-1, 1), (0, float('nan')), (0, float('inf'))])
def test_invalid_segment_intervals(start, end):
    with pytest.raises(ValidationError):
        Segment(id=0, start=start, end=end, text='text')


def test_invalid_sequence_and_duration():
    with pytest.raises(ValidationError):
        result([Segment(id=1, start=0, end=1, text='text')])
    with pytest.raises(ValidationError):
        result([Segment(id=0, start=0, end=2, text='text')])
    with pytest.raises(ValidationError):
        result([Segment(id=0, start=0, end=.8, text='a'), Segment(id=1, start=.5, end=1, text='b')])


def test_adapter_timeout(tmp_path):
    provider = FasterWhisperProvider(Settings())
    with patch('app.transcription.provider.subprocess.run', side_effect=subprocess.TimeoutExpired('python', 1)):
        with pytest.raises(ServiceError, match='timed out'):
            provider.transcribe(tmp_path / 'audio.wav', None)


@pytest.mark.parametrize('payload,code', [
    ({'error_code': 'provider_unavailable'}, 'provider_unavailable'),
    ({'error_code': 'model_unavailable'}, 'model_unavailable'),
    ({'error_code': 'unsupported_language'}, 'unsupported_language'),
    ({'invalid': True}, 'invalid_transcript'),
])
def test_adapter_failure_payload(tmp_path, payload, code):
    def execute(args, **kwargs):
        Path(args[4]).write_text(json.dumps(payload))
    with patch('app.transcription.provider.subprocess.run', side_effect=execute):
        with pytest.raises(ServiceError) as caught:
            FasterWhisperProvider(Settings()).transcribe(tmp_path / 'audio.wav', None)
    assert caught.value.code == code


def test_adapter_success(tmp_path):
    def execute(args, **kwargs):
        assert kwargs['timeout'] == 77
        Path(args[4]).write_text(result().model_dump_json())
    with patch('app.transcription.provider.subprocess.run', side_effect=execute):
        assert FasterWhisperProvider(Settings(transcription_timeout_seconds=77)).transcribe(tmp_path / 'audio.wav', 'en').text == 'Hello world.'


def test_busy_and_capacity_released_after_failure(setup):
    from app.storage.local import LocalVideoStorage
    from app.transcription.service import TranscriptionService
    from app.models.transcript import TranscriptRequest
    settings, video, repo = setup
    service = TranscriptionService(settings, repo, LocalVideoStorage(settings.storage_root),
                                   JsonTranscriptRepository(settings.storage_root), FakeProvider())
    service.capacity.acquire()
    with pytest.raises(ServiceError) as caught:
        service.create(video.id, TranscriptRequest())
    assert caught.value.code == 'transcription_busy'
    service.capacity.release()
    assert service.create(video.id, TranscriptRequest()).status == 'completed'


class IdentifiedProvider:
    calls = 0
    revision = 'commit-a'

    def reuse_identity(self, language):
        return dict(provider='known', provider_version='1', engine_version='1', model='fixture',
                    model_revision=self.revision, adapter_version='test-v1', parameters={'language': language})

    def transcribe(self, audio, language):
        self.calls += 1
        return result().model_copy(update=self.reuse_identity(language))


def test_reuse_survives_restart_and_preserves_history(setup):
    provider = IdentifiedProvider()
    url = f'/videos/{setup[1].id}/transcriptions'
    fresh = client_for(setup, provider).post(url, json={}).json()
    client = client_for(setup, provider)
    hit = client.post(url, json={'reuse_completed': True})
    assert hit.status_code == 200 and hit.json() == fresh
    assert provider.calls == 1 and client.get(url).json() == [fresh]
    forced = client.post(url, json={'reuse_completed': False})
    assert forced.status_code == 201 and forced.json()['id'] != fresh['id']
    assert provider.calls == 2


def test_reuse_invalidates_on_input_or_identity_change(setup):
    settings, video, _ = setup
    provider = IdentifiedProvider()
    url = f'/videos/{video.id}/transcriptions'
    client = client_for(setup, provider)
    body = {'reuse_completed': True}
    assert client.post(url, json=body).status_code == 201
    en = dict(**body, language='en')
    assert client.post(url, json=en).status_code == 201
    provider.revision = 'commit-b'
    assert client.post(url, json=en).status_code == 201
    wav = settings.storage_root / str(video.id) / 'audio.wav'
    data = wav.read_bytes()
    wav.write_bytes(data[:-2] + b'\1\0')
    assert client.post(url, json=en).status_code == 201
    assert client.post(url, json=en).status_code == 200
    assert provider.calls == 4


def test_unidentified_provider_and_failed_runs_do_not_hit(setup):
    url = f'/videos/{setup[1].id}/transcriptions'
    body = {'reuse_completed': True}
    client = client_for(setup)
    assert all(client.post(url, json=body).status_code == 201 for _ in range(2))

    class Flaky(IdentifiedProvider):
        def transcribe(self, audio, language):
            if self.calls == 0:
                self.calls += 1
                raise ServiceError('transcription_failed', 'Failed')
            return super().transcribe(audio, language)

    provider = Flaky()
    client = client_for(setup, provider)
    assert client.post(url, json=body).json()['status'] == 'failed'
    assert client.post(url, json=body).status_code == 201
    assert client.post(url, json=body).status_code == 200
    assert provider.calls == 2


def test_background_analyze_reuses_transcript_checkpoint(setup):
    from test_jobs import until

    provider = IdentifiedProvider()
    root = f'/videos/{setup[1].id}'
    with client_for(setup, provider) as client:
        run = client.post(root + '/transcriptions', json={}).json()
        job = client.post(root + '/jobs', json={'action': 'analyze', 'key': str(uuid4())}).json()
        done = until(client, setup[1].id, job['id'])
        assert done['outputs']['transcript'] == run['id']
        assert provider.calls == 1
