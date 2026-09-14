from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4
import hashlib
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.models.video import ExtractionInfo
from app.shared.config import Settings
from app.shared.errors import ServiceError
from app.storage.local import LocalVideoStorage

class FakeMedia:
    def probe(self, source: Path, extension: str) -> float:
        return 1.0

    def extract(self, source: Path, target: Path) -> ExtractionInfo:
        target.write_bytes(b"test audio")
        return ExtractionInfo(ffmpeg_version="test")

@pytest.fixture
def setup(tmp_path):
    settings = Settings(storage_root=tmp_path, max_video_bytes=1024)
    return settings, TestClient(create_app(settings, media=FakeMedia()))

def test_health(setup):
    _, client = setup
    assert client.get("/health").json() == {"status": "ok", "version": "0.1.0"}

def test_upload_and_persistent_status(setup):
    settings, client = setup
    response = client.post("/videos", files={"file": ("clip.mp4", b"video", "video/mp4")})
    assert response.status_code == 201
    data = response.json()
    video_id = UUID(data["id"])
    assert data["status"] == "completed"
    assert data["sha256"] == hashlib.sha256(b"video").hexdigest()
    assert data["size_bytes"] == 5
    assert data["extraction"]["adapter_version"] == "ffmpeg-wav-v1"
    assert (settings.storage_root / str(video_id) / "original").read_bytes() == b"video"
    restarted = TestClient(create_app(settings, media=FakeMedia()))
    assert restarted.get(f"/videos/{video_id}").json() == data

@pytest.mark.parametrize("filename,mime,payload,status", [
    ("x.exe", "video/mp4", b"x", 415),
    ("x.mp4", "text/plain", b"x", 415),
    ("x.mp4", "video/mp4", b"", 422),
    ("x.mp4", "video/mp4", b"x" * 1025, 413),
])
def test_rejected_uploads_cleanup(setup, filename, mime, payload, status):
    settings, client = setup
    response = client.post("/videos", files={"file": (filename, payload, mime)})
    assert response.status_code == status
    assert not list(settings.storage_root.iterdir())

def test_exact_limit_and_unique_ids(setup):
    _, client = setup
    ids = [
        client.post("/videos", files={"file": ("x.mp4", b"x"*1024, "video/mp4")}).json()["id"]
        for _ in range(2)
    ]
    assert ids[0] != ids[1]

def test_filename_is_not_used_as_path(setup):
    settings, client = setup
    data = client.post("/videos", files={"file": ("../../escape.mp4", b"x", "video/mp4")}).json()
    assert data["original_filename"] == "escape.mp4"
    assert [p.name for p in settings.storage_root.iterdir()] == [data["id"]]

def test_probe_failure_removes_input(tmp_path):
    class Invalid(FakeMedia):
        def probe(self, source, extension):
            raise ServiceError("invalid_media", "Invalid media.")
    client = TestClient(create_app(Settings(storage_root=tmp_path), media=Invalid()))
    assert client.post("/videos", files={"file": ("x.mp4", b"x", "video/mp4")}).status_code == 422
    assert not list(tmp_path.iterdir())

def test_processing_failure_is_persisted(tmp_path):
    class Failing(FakeMedia):
        def extract(self, source, target):
            raise ServiceError("media_timeout", "Timed out.", 504)
    client = TestClient(create_app(Settings(storage_root=tmp_path), media=Failing()))
    response = client.post("/videos", files={"file": ("x.mp4", b"x", "video/mp4")})
    assert response.status_code == 201  # Video resource exists; status reports extraction failure.
    data = response.json()
    assert data["status"] == "failed"
    assert data["error_code"] == "media_timeout"
    assert client.get("/videos/" + data["id"]).json() == data

def test_unknown_and_invalid_id(setup):
    _, client = setup
    assert client.get(f"/videos/{uuid4()}").status_code == 404
    assert client.get("/videos/not-a-uuid").status_code == 422

def test_missing_and_extra_fields(setup):
    _, client = setup
    assert client.post("/videos", files={"other": ("x.mp4", b"x", "video/mp4")}).status_code == 422
    assert client.post("/videos", json={}).status_code == 415
    response = client.post("/videos", files=[
        ("file", ("x.mp4", b"x", "video/mp4")),
        ("file", ("y.mp4", b"x", "video/mp4")),
    ])
    assert response.status_code == 400

def test_request_limit_even_without_content_length(setup):
    settings, client = setup
    response = client.post(
        "/videos", content=iter([b"x"*40000, b"x"*40000]),
        headers={"Content-Type": "multipart/form-data; boundary=test"},
    )
    assert response.status_code == 413
    assert not list(settings.storage_root.iterdir())

def test_storage_read_failure_removes_partial(tmp_path):
    class Broken(BytesIO):
        def read(self, size=-1):
            raise OSError("disk/network failure")
    storage = LocalVideoStorage(tmp_path)
    with pytest.raises(OSError):
        storage.save(uuid4(), Broken(b"x"), 100)
    assert not list(tmp_path.iterdir())
