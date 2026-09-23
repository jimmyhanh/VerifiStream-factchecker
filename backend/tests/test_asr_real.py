"""Opt-in model test: ASR_TEST_AUDIO points at whisper.cpp's public JFK sample."""
import os
import wave
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.models.video import VideoRecord, VideoStatus
from app.database.repository import JsonVideoRepository
from app.shared.config import Settings

pytestmark = [pytest.mark.asr, pytest.mark.skipif(not os.getenv('ASR_TEST_AUDIO'),
              reason='Set ASR_TEST_AUDIO to the documented JFK WAV fixture to run real inference')]


def test_real_speech_transcription_and_silence(tmp_path):
    settings = Settings(storage_root=tmp_path, model_cache=Path(os.getenv('MODEL_CACHE', 'storage/models')))
    fixture = Path(os.environ['ASR_TEST_AUDIO'])
    video = VideoRecord(id=uuid4(), status=VideoStatus.completed, original_filename='speech.mp4',
                        size_bytes=fixture.stat().st_size, sha256='fixture', duration_seconds=11)
    JsonVideoRepository(tmp_path).save(video)
    audio = tmp_path / str(video.id) / 'audio.wav'
    audio.write_bytes(fixture.read_bytes())
    client = TestClient(create_app(settings))
    url = f'/videos/{video.id}'
    response = client.post(url + '/transcriptions', json={'language': 'en'})
    assert response.status_code == 201
    record = response.json()
    assert record['status'] == 'completed', record
    assert 'country' in record['text'].lower(), record
    assert record['result']['segments']
    assert record['result']['model_revision'] != 'main'
    assert client.get(url + '/transcript').json() == record
    # A separate silent input must not invent a statement.
    silent = video.model_copy(update={'id': uuid4()})
    JsonVideoRepository(tmp_path).save(silent)
    with wave.open(str(tmp_path / str(silent.id) / 'audio.wav'), 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b'\0\0' * 32000)
    result = client.post(f'/videos/{silent.id}/transcriptions', json={}).json()
    assert result['status'] == 'completed', result
    assert result['text'] == ''
    assert result['result']['segments'] == []
