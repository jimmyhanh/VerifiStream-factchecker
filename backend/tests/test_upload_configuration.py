"""Longer uploads retain hard boundaries and operator overrides."""
import json
import subprocess
from pathlib import Path
from unittest.mock import patch
import pytest
from app.media.ffmpeg import FFmpegProcessor
from app.shared.config import Settings
from app.shared.errors import ServiceError


@pytest.mark.parametrize('duration,accepted', [(1800, True), (1800.01, False)])
def test_default_duration_boundary(monkeypatch, duration, accepted):
    for key in ('MAX_DURATION_SECONDS','MAX_VIDEO_BYTES','PROCESS_TIMEOUT_SECONDS','TRANSCRIPTION_TIMEOUT_SECONDS'):
        monkeypatch.delenv(key, raising=False)
    settings=Settings.from_env()
    assert settings.max_video_bytes==524288000
    assert settings.transcription_timeout_seconds==1800
    metadata={'format':{'format_name':'mov,mp4','duration':str(duration)},
              'streams':[{'codec_type':'video'},{'codec_type':'audio'}]}
    def execute(args, **kwargs):
        assert kwargs['timeout']==600
        return subprocess.CompletedProcess(args,0,stdout=json.dumps(metadata))
    with patch('app.media.ffmpeg.subprocess.run',side_effect=execute):
        if accepted:
            assert FFmpegProcessor(settings).probe(Path('video.mp4'),'.mp4')==duration
        else:
            with pytest.raises(ServiceError) as caught:
                FFmpegProcessor(settings).probe(Path('video.mp4'),'.mp4')
            assert caught.value.code=='video_too_long'


def test_existing_operator_overrides_preserved(monkeypatch):
    values={'MAX_DURATION_SECONDS':'600','MAX_VIDEO_BYTES':'104857600',
            'PROCESS_TIMEOUT_SECONDS':'120','TRANSCRIPTION_TIMEOUT_SECONDS':'900'}
    for key,value in values.items():monkeypatch.setenv(key,value)
    settings=Settings.from_env()
    assert (settings.max_duration_seconds,settings.max_video_bytes,
            settings.process_timeout_seconds,settings.transcription_timeout_seconds)==(600,104857600,120,900)
