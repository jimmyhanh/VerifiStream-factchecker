import json
import subprocess
from pathlib import Path
from unittest.mock import patch
import pytest
from app.media.ffmpeg import FFmpegProcessor
from app.shared.config import Settings
from app.shared.errors import ServiceError

def probe_payload(kinds=("video", "audio"), duration="1", container="mov,mp4"):
    return subprocess.CompletedProcess([], 0, json.dumps({
        "format": {"duration": duration, "format_name": container},
        "streams": [{"codec_type": kind} for kind in kinds],
    }), "")

@pytest.mark.parametrize("payload,code", [
    (probe_payload(kinds=("video",)), "no_audio_stream"),
    (probe_payload(kinds=("audio",)), "no_video_stream"),
    (probe_payload(duration="nan"), "invalid_media"),
    (probe_payload(duration="0"), "invalid_media"),
    (probe_payload(duration="601"), "video_too_long"),
    (probe_payload(container="avi"), "invalid_media"),
])
def test_probe_validates_actual_media(payload, code):
    media = FFmpegProcessor(Settings())
    with patch.object(media, "_run", return_value=payload):
        with pytest.raises(ServiceError) as error:
            media.probe(Path("input"), ".mp4")
    assert error.value.code == code

@pytest.mark.parametrize("failure,code", [
    (FileNotFoundError(), "media_tool_unavailable"),
    (subprocess.TimeoutExpired("ffmpeg", 1), "media_timeout"),
    (subprocess.CalledProcessError(1, "ffmpeg"), "invalid_media"),
])
def test_subprocess_errors(failure, code):
    with patch("app.media.ffmpeg.subprocess.run", side_effect=failure):
        with pytest.raises(ServiceError) as error:
            FFmpegProcessor(Settings())._run(["ffmpeg"])
    assert error.value.code == code

def test_failed_extraction_cleans_partial_output(tmp_path):
    media = FFmpegProcessor(Settings())
    target = tmp_path / "audio.wav"
    def execute(args):
        if "-version" in args:
            return subprocess.CompletedProcess(args, 0, "ffmpeg version test\n", "")
        Path(args[-1]).write_bytes(b"partial")
        raise ServiceError("media_timeout", "Timed out.", 504)
    with patch.object(media, "_run", side_effect=execute):
        with pytest.raises(ServiceError):
            media.extract(tmp_path / "original", target)
    assert not target.exists()
    assert not target.with_suffix(".part.wav").exists()
