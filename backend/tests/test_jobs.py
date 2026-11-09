import time
from threading import Event
from uuid import UUID, uuid4
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import create_app
from app.shared.config import Settings
from app.jobs.service import LocalJobs, Job, JobRequest
from app.videos.deletion import VideoActivity
from test_api import FakeMedia as BaseMedia
import wave
from app.models.video import ExtractionInfo


class FakeMedia(BaseMedia):
    def extract(self, source, target):
        with wave.open(str(target), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\0\0" * 16000)
        return ExtractionInfo(ffmpeg_version="fixture")


from test_transcription import FakeProvider


def until(client, video, job):
    for _ in range(100):
        result = client.get(f"/videos/{video}/jobs/{job}").json()
        if result["status"] not in ("queued", "running"):
            return result
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_analyze_refresh_and_idempotency(tmp_path):
    app = create_app(
        Settings(storage_root=tmp_path),
        media=FakeMedia(),
        transcription_provider=FakeProvider(),
    )
    with TestClient(app) as client:
        video = client.post(
            "/videos", files={"file": ("x.mp4", b"x", "video/mp4")}
        ).json()["id"]
        payload = {"key": str(uuid4()), "action": "analyze", "input": {}}
        response = client.post(f"/videos/{video}/jobs", json=payload)
        assert response.status_code == 202, response.text
        result = until(client, video, response.json()["id"])
        assert result["status"] == "needs_review", result
        assert set(result["outputs"]) == {"transcript", "claims", "atoms"}
        assert (
            client.post(f"/videos/{video}/jobs", json=payload).json()["id"]
            == result["id"]
        )
        assert (
            client.post(
                f"/videos/{video}/jobs", json={**payload, "action": "transcript"}
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"/videos/{video}/jobs",
                json={"key": str(uuid4()), "action": "claims", "input": {}},
            ).status_code
            == 422
        )
    with TestClient(
        create_app(Settings(storage_root=tmp_path), media=FakeMedia())
    ) as restarted:
        assert (
            restarted.get(f'/videos/{video}/jobs/{result["id"]}').json()["outputs"]
            == result["outputs"]
        )
        assert restarted.delete(f"/videos/{video}").status_code == 200
        assert not (tmp_path / video).exists()


def test_queued_cancel_and_deletion_block(tmp_path):
    entered, release = Event(), Event()

    class Slow(FakeProvider):
        def transcribe(self, *args):
            entered.set()
            assert release.wait(5)
            return super().transcribe(*args)

    with TestClient(
        create_app(
            Settings(storage_root=tmp_path),
            media=FakeMedia(),
            transcription_provider=Slow(),
        )
    ) as client:
        video = client.post(
            "/videos", files={"file": ("x.mp4", b"x", "video/mp4")}
        ).json()["id"]

        def submit():
            return client.post(
                f"/videos/{video}/jobs",
                json={"key": str(uuid4()), "action": "transcript", "input": {}},
            ).json()

        first = submit()
        assert entered.wait(2)
        second = submit()
        try:
            assert client.delete(f"/videos/{video}").status_code == 409
            assert (
                client.post(
                    f'/videos/{video}/jobs/{first["id"]}/cancel', json={}
                ).status_code
                == 409
            )
            assert (
                client.post(
                    f'/videos/{video}/jobs/{second["id"]}/cancel', json={}
                ).json()["status"]
                == "cancelled"
            )
            assert client.get("/health").status_code == 200
        finally:
            release.set()
        assert until(client, video, first["id"])["status"] == "completed"


def test_recovery_single_owner_and_checkpoint_retry(tmp_path):
    video = uuid4()
    activity = VideoActivity()
    calls = []

    def execute(job, save):
        calls.append(dict(job.outputs))
        save(job, "done", uuid4())

    queue = LocalJobs(tmp_path, activity, execute, lambda *_: None, "v1")
    old = Job(
        video_id=video,
        request=JobRequest(key=uuid4(), action="analyze"),
        configuration="v1",
        status="running",
        outputs={"transcript": uuid4()},
    )
    queue._save(old)
    queue.start()
    try:
        assert queue.get(video, old.id).status == "interrupted"
        import pytest

        second = LocalJobs(tmp_path, VideoActivity(), execute, lambda *_: None, "v1")
        with pytest.raises(RuntimeError):
            second.start()
        retry = queue.retry(video, old.id, uuid4())
        for _ in range(100):
            if queue.get(video, retry.id).status == "needs_review":
                break
            time.sleep(0.01)
        assert calls == [old.outputs]
        assert queue.get(video, old.id).status == "interrupted"
        assert queue.get(video, retry.id).retry_of == old.id
    finally:
        queue.close()


def test_failure_sanitization_and_explicit_retry_keeps_checkpoint(tmp_path):
    from app.shared.errors import ServiceError

    video = uuid4()
    calls = []

    def execute(job, save):
        if "transcript" not in job.outputs:
            calls.append("transcript")
            save(job, "transcript", uuid4())
        if job.retry_of is None:
            raise RuntimeError("secret-provider-token")
        calls.append("claims")
        save(job, "claims", uuid4())

    queue = LocalJobs(tmp_path, VideoActivity(), execute, lambda *_: None, "v1")
    queue.start()

    def wait(job):
        for _ in range(100):
            record = queue.get(video, job.id)
            if record.status not in ("queued", "running"):
                return record
            time.sleep(0.01)
        raise AssertionError("timeout")

    try:
        failed = wait(queue.submit(video, JobRequest(key=uuid4(), action="analyze")))
        assert failed.status == "failed"
        assert "secret" not in failed.model_dump_json()
        retried = wait(queue.retry(video, failed.id, uuid4()))
        assert retried.status == "needs_review"
        assert calls == ["transcript", "claims"]
        queue.configuration = "v2"
        import pytest

        with pytest.raises(ServiceError, match="Configuration changed"):
            queue.retry(video, failed.id, uuid4())
    finally:
        queue.close()


def test_queue_bound_and_queued_recovery(tmp_path):
    from app.shared.errors import ServiceError
    import pytest

    entered, release = Event(), Event()
    video = uuid4()

    def execute(job, save):
        entered.set()
        release.wait(5)

    queue = LocalJobs(tmp_path, VideoActivity(), execute, lambda *_: None, "v1")
    for _ in range(100):
        queue._save(
            Job(
                video_id=video,
                request=JobRequest(key=uuid4(), action="transcript"),
                configuration="v1",
            )
        )
    queue.start()
    try:
        assert entered.wait(2)
        with pytest.raises(ServiceError, match="Queue is full"):
            queue.submit(video, JobRequest(key=uuid4(), action="transcript"))
        assert queue.activity.active == 100
    finally:
        queue.stop.set()
        release.set()
        queue.close()
    assert queue.activity.active == 0


from test_ranking import ranking
from test_mapping import mapping
from test_retrieval import setup


def test_findings_pipeline_uses_exact_mapping_and_saved_confidence(ranking):
    config, client, base, source = ranking
    with client:
        response = client.post(
            base + "/jobs",
            json={
                "key": str(uuid4()),
                "action": "findings",
                "input": {"mapping_run_id": source["id"]},
            },
        )
        assert response.status_code == 202, response.text
        video = base.split("/")[-1]
        job = until(client, video, response.json()["id"])
        assert job["status"] == "completed", job
        assert set(job["outputs"]) == {"ranking", "verification", "confidence"}
        result = client.get(
            base + "/confidence-runs/" + job["outputs"]["confidence"]
        ).json()
        assert (
            result["request"]["verification_run_id"] == job["outputs"]["verification"]
        )

def test_idle_scan_tolerates_concurrent_terminal_history_deletion(tmp_path,monkeypatch):
    queue=LocalJobs(tmp_path,VideoActivity(),lambda *_:None,lambda *_:None,'v1')
    job=Job(video_id=uuid4(),request=JobRequest(key=uuid4(),action='analyze'),configuration='v1',status='completed')
    queue._save(job)
    original=Path.read_text
    def read(path,*args,**kwargs):
        if path.name==f'{job.id}.json':raise FileNotFoundError()
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',read)
    assert queue._all()==[]


def test_background_upload_returns_before_extraction_and_survives_refresh(tmp_path):
    entered, release = Event(), Event()

    class SlowMedia(FakeMedia):
        def extract(self, source, target):
            entered.set()
            assert release.wait(5)
            return super().extract(source, target)

    settings = Settings(storage_root=tmp_path)
    with TestClient(create_app(settings, media=SlowMedia())) as client:
        response = client.post("/videos?background=true", files={"file": ("x.mp4", b"x", "video/mp4")})
        assert response.status_code == 202, response.text
        assert response.json()["status"] == "queued"
        video = response.json()["id"]
        try:
            assert entered.wait(2)
            assert client.get(f"/videos/{video}").json()["status"] == "processing"
            assert client.delete(f"/videos/{video}").status_code == 409
            assert client.post(f"/videos/{video}/jobs", json={"key":str(uuid4()), "action":"analyze"}).status_code == 409
            job = client.get(f"/videos/{video}/jobs").json()[0]
        finally:
            release.set()
        assert until(client, video, job["id"])["status"] == "completed"
    with TestClient(create_app(settings, media=FakeMedia())) as restarted:
        assert restarted.get(f"/videos/{video}").json()["status"] == "completed"
        assert restarted.get("/videos").json()[0]["extraction"]["sample_rate"] == 16000


def test_background_upload_rolls_back_without_worker(tmp_path):
    client = TestClient(create_app(Settings(storage_root=tmp_path), media=FakeMedia()))
    response = client.post("/videos?background=true", files={"file": ("x.mp4", b"x", "video/mp4")})
    assert response.status_code == 503
    assert client.get("/videos").json() == []


def test_failed_audio_can_retry_without_another_upload(tmp_path):
    from app.shared.errors import ServiceError

    class FailOnce(FakeMedia):
        failed = False

        def extract(self, source, target):
            if not self.failed:
                self.failed = True
                raise ServiceError("decode_failed", "Could not decode audio.")
            return super().extract(source, target)

    with TestClient(create_app(Settings(storage_root=tmp_path), media=FailOnce())) as client:
        video = client.post("/videos?background=true", files={"file": ("x.mp4", b"x", "video/mp4")}).json()["id"]
        job = client.get(f"/videos/{video}/jobs").json()[0]
        assert until(client, video, job["id"])["error_code"] == "decode_failed"
        assert client.get(f"/videos/{video}").json()["error_message"] == "Could not decode audio."
        retry = client.post(f"/videos/{video}/jobs/{job['id']}/retry", json={"key":str(uuid4())}).json()
        assert until(client, video, retry["id"])["status"] == "completed"
        assert client.get(f"/videos/{video}").json()["error_code"] is None
