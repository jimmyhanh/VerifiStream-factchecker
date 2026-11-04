from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID, uuid4
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.shared.config import Settings
from app.storage.local import LocalVideoStorage
from app.videos.deletion import VideoActivity
from test_api import setup, FakeMedia


def upload(client, name="sample.mp4"):
    r = client.post("/videos", files={"file": (name, b"fixture", "video/mp4")})
    assert r.status_code == 201, r.text
    return r.json()


def test_delete_all_related_records_preserves_model_cache(setup):
    config, client = setup
    video = upload(client)
    folder = config.storage_root / video["id"]
    for name in (
        "transcriptions",
        "decompositions",
        "proposition-drafts",
        "retrievals",
        "evidence-mappings",
        "verifications",
        "confidence-runs",
    ):
        (folder / name).mkdir()
        (folder / name / "saved.json").write_text("{}")
    cache = config.storage_root / "models"
    cache.mkdir()
    (cache / "model.bin").write_bytes(b"cached")
    response = client.delete("/videos/" + video["id"])
    assert response.status_code == 200 and response.json()["deleted_ids"] == [
        video["id"]
    ]
    assert not response.json()["pending_cleanup"] and not folder.exists()
    assert (cache / "model.bin").read_bytes() == b"cached"
    assert client.get("/videos/" + video["id"]).status_code == 404
    assert client.get("/videos").json() == []
    assert client.delete("/videos/" + video["id"]).status_code == 404


def test_clear_requires_confirmation_and_unchanged_inventory(setup):
    config, client = setup
    a = upload(client)
    b = upload(client)
    preview = client.get("/videos/deletion-preview").json()
    assert preview["count"] == 2
    body = {"confirmation": "DELETE_ALL_VIDEOS", "video_ids": preview["video_ids"]}
    assert (
        client.request(
            "DELETE", "/videos", json={"video_ids": preview["video_ids"]}
        ).status_code
        == 422
    )
    extra = upload(client)
    assert client.request("DELETE", "/videos", json=body).status_code == 409
    assert len(client.get("/videos").json()) == 3
    body["video_ids"] = client.get("/videos/deletion-preview").json()["video_ids"]
    assert set(
        client.request("DELETE", "/videos", json=body).json()["deleted_ids"]
    ) == {a["id"], b["id"], extra["id"]}
    assert client.get("/videos").json() == []
    assert (
        client.request(
            "DELETE",
            "/videos",
            json={"confirmation": "DELETE_ALL_VIDEOS", "video_ids": []},
        ).status_code
        == 200
    )


def test_active_upload_blocks_delete_and_clear(tmp_path):
    entered, release = Event(), Event()

    class Blocking(FakeMedia):
        def extract(self, source, target):
            entered.set()
            assert release.wait(5)
            return super().extract(source, target)

    client = TestClient(create_app(Settings(storage_root=tmp_path), media=Blocking()))
    with ThreadPoolExecutor() as pool:
        future = pool.submit(upload, client)
        assert entered.wait(2)
        try:
            assert client.delete("/videos/" + str(uuid4())).status_code == 409
            assert (
                client.request(
                    "DELETE",
                    "/videos",
                    json={"confirmation": "DELETE_ALL_VIDEOS", "video_ids": []},
                ).status_code
                == 409
            )
            assert client.get("/health").status_code == 200
        finally:
            release.set()
        record = future.result()
    assert client.delete("/videos/" + record["id"]).status_code == 200


def test_delete_blocks_new_operations_and_never_resurrects_files(setup):
    config, client = setup
    record = upload(client)
    entered, release = Event(), Event()
    original = LocalVideoStorage.delete

    def blocked(self, video_id):
        entered.set()
        assert release.wait(5)
        return original(self, video_id)

    with patch.object(
        LocalVideoStorage, "delete", blocked
    ), ThreadPoolExecutor() as pool:
        future = pool.submit(client.delete, "/videos/" + record["id"])
        assert entered.wait(2)
        try:
            assert (
                client.post(
                    "/videos/" + record["id"] + "/transcriptions", json={}
                ).status_code
                == 409
            )
            assert client.get("/videos").status_code == 409
            assert client.get("/health").status_code == 200
        finally:
            release.set()
        assert future.result().status_code == 200
    assert not (config.storage_root / record["id"]).exists()


def test_incomplete_cleanup_is_reported_and_clear_retries_tombstones(setup):
    config, client = setup
    record = upload(client)
    with patch("app.storage.local.shutil.rmtree", side_effect=OSError("locked")):
        response = client.delete("/videos/" + record["id"])
    assert response.json()["pending_cleanup"] is True
    assert client.get("/videos").json() == []
    assert list((config.storage_root / ".deleted").iterdir())
    response = client.request(
        "DELETE", "/videos", json={"confirmation": "DELETE_ALL_VIDEOS", "video_ids": []}
    )
    assert response.json()["pending_cleanup"] is False
    assert not list((config.storage_root / ".deleted").iterdir())


def test_failed_rename_does_not_claim_success(setup):
    from pathlib import Path

    config, client = setup
    record = upload(client)
    with patch.object(Path, "rename", side_effect=OSError("permission")):
        response = client.delete("/videos/" + record["id"])
    assert response.status_code == 503
    assert client.get("/videos/" + record["id"]).status_code == 200


def test_delete_cors_and_invalid_id(setup):
    _, client = setup
    r = client.options(
        "/videos",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert (
        r.status_code == 200 and "DELETE" in r.headers["access-control-allow-methods"]
    )
    assert client.delete("/videos/not-a-uuid").status_code == 422
