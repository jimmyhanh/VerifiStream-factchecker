import shutil
import subprocess
import wave
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.shared.config import Settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
        reason="FFmpeg and FFprobe are required",
    ),
]

def make_video(path: Path, audio: bool = True) -> None:
    command = ["ffmpeg", "-nostdin", "-y", "-v", "error",
               "-f", "lavfi", "-i", "color=c=blue:s=64x64:r=10:d=1"]
    if audio:
        command += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                    "-c:a", "aac", "-shortest"]
    command += ["-c:v", "mpeg4", str(path)]
    subprocess.run(command, check=True, capture_output=True, timeout=30)

def test_real_video_to_pcm_wav(tmp_path):
    sample = tmp_path / "sample.mp4"
    make_video(sample)
    settings = Settings(storage_root=tmp_path / "storage")
    client = TestClient(create_app(settings))
    with sample.open("rb") as file:
        response = client.post("/videos", files={"file": ("sample.mp4", file, "video/mp4")})
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "completed", data
    with wave.open(str(settings.storage_root / data["id"] / "audio.wav"), "rb") as audio:
        assert (audio.getnchannels(), audio.getframerate(), audio.getsampwidth()) == (1, 16000, 2)
        assert 0.9 <= audio.getnframes() / 16000 <= 1.2
    assert client.get("/videos/" + data["id"]).json() == data

def test_real_video_without_audio(tmp_path):
    sample = tmp_path / "silent.mp4"
    make_video(sample, audio=False)
    root = tmp_path / "storage"
    client = TestClient(create_app(Settings(storage_root=root)))
    with sample.open("rb") as file:
        response = client.post("/videos", files={"file": ("silent.mp4", file, "video/mp4")})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "no_audio_stream"
    assert not list(root.iterdir())

def test_spoofed_video_rejected_by_ffprobe(tmp_path):
    client = TestClient(create_app(Settings(storage_root=tmp_path)))
    response = client.post("/videos", files={"file": ("fake.mp4", b"not a video", "video/mp4")})
    assert response.status_code == 422
    assert not list(tmp_path.iterdir())
