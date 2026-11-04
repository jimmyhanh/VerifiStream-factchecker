"""Durable local job adapter. One process/worker; no automatic replay of interrupted calls."""

import json
import logging
import threading
from pathlib import Path
from typing import Callable, Literal
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.models.video import utc_now
from app.shared.errors import ServiceError
from app.videos.deletion import VideoActivity

Action = Literal[
    "analyze",
    "findings",
    "transcript",
    "claims",
    "atoms",
    "retrieval",
    "mapping",
    "ranking",
    "verification",
    "confidence",
]


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: UUID
    action: Action
    input: dict = Field(default_factory=dict)


class Job(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    video_id: UUID
    request: JobRequest
    status: Literal[
        "queued",
        "running",
        "completed",
        "needs_review",
        "failed",
        "interrupted",
        "cancelled",
    ] = "queued"
    stage: str = "queued"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    outputs: dict[str, UUID] = Field(default_factory=dict)
    error_code: str | None = None
    retry_of: UUID | None = None
    configuration: str


class LocalJobs:
    def __init__(
        self,
        root: Path,
        activity: VideoActivity,
        execute: Callable,
        validate: Callable,
        configuration: str,
    ):
        self.root, self.activity, self.execute, self.validate, self.configuration = (
            root,
            activity,
            execute,
            validate,
            configuration,
        )
        self.mutex = threading.RLock()
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.ready = False
        self.thread = None
        self.file = None

    def _save(self, job: Job) -> None:
        directory = self.root / str(job.video_id) / "jobs"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{job.id}.json"
        temporary = directory / f"{uuid4()}.tmp"
        job.updated_at = utc_now()
        try:
            with temporary.open("w", encoding="utf8") as file:
                file.write(job.model_dump_json(indent=2))
                file.flush()
                import os

                os.fsync(file.fileno())
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    def _all(self) -> list[Job]:
        jobs = []
        for path in self.root.glob("*/jobs/*.json"):
            try:
                jobs.append(Job.model_validate_json(path.read_text()))
            except FileNotFoundError:
                # Terminal video history can be deleted during an idle scan.
                continue
        return sorted(jobs, key=lambda j: (j.created_at, str(j.id)))

    def start(self) -> None:
        # Docker/Linux contract. Refuse a second owner instead of corrupting JSON history.
        import fcntl

        self.root.mkdir(parents=True, exist_ok=True)
        self.file = (self.root / ".jobs-worker.lock").open("a+")
        try:
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:
            self.file.close()
            raise RuntimeError("Only one API worker may own this storage directory")
        with self.mutex:
            pending = 0
            for job in self._all():
                if job.status == "running":
                    job.status = "interrupted"
                    job.error_code = "worker_interrupted"
                    self._save(job)
                if job.status == "queued":
                    pending += 1
            with self.activity.lock:
                self.activity.active += pending
            self.ready = True
            self.stop.clear()
            self.thread = threading.Thread(
                target=self._loop, name="verifistream-jobs", daemon=True
            )
            self.thread.start()

    def close(self) -> None:
        self.ready = False
        self.stop.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=5)
        # Running thread retains the file lock until it exits.

    def list(self, video: UUID) -> list[Job]:
        with self.mutex:
            return [j for j in reversed(self._all()) if j.video_id == video][:100]

    def get(self, video: UUID, job_id: UUID) -> Job:
        try:
            return Job.model_validate_json(
                (self.root / str(video) / "jobs" / f"{job_id}.json").read_text()
            )
        except FileNotFoundError:
            raise ServiceError("job_not_found", "Job not found.", 404)

    def submit(
        self, video: UUID, request: JobRequest, previous: Job | None = None
    ) -> Job:
        if not self.ready or not self.thread or not self.thread.is_alive():
            raise ServiceError(
                "worker_unavailable", "Background worker is not running.", 503
            )
        # Validate input before admission; exact input retained for idempotency comparison.
        self.validate(video, request)
        with self.mutex:
            jobs = self._all()
            for old in jobs:
                if old.video_id == video and old.request.key == request.key:
                    if old.request != request:
                        raise ServiceError(
                            "idempotency_conflict",
                            "This request key was used with different input.",
                            409,
                        )
                    return old
            if sum(j.status in ("queued", "running") for j in jobs) >= 100:
                raise ServiceError(
                    "queue_full", "Queue is full. Wait for work to finish.", 429
                )
            job = Job(
                video_id=video,
                request=request,
                configuration=self.configuration,
                retry_of=previous.id if previous else None,
                outputs=dict(previous.outputs) if previous else {},
            )
            with self.activity.lock:
                if self.activity.deleting:
                    raise ServiceError(
                        "videos_deleting", "Deletion is in progress.", 409
                    )
                self._save(job)
                self.activity.active += 1
            self.wake.set()
            return job

    def retry(self, video: UUID, job_id: UUID, key: UUID) -> Job:
        with self.mutex:
            job = self.get(video, job_id)
            if job.status not in ("failed", "interrupted"):
                raise ServiceError(
                    "job_not_retryable",
                    "Only failed or interrupted jobs can be retried.",
                    409,
                )
            if job.configuration != self.configuration:
                raise ServiceError(
                    "job_configuration_changed",
                    "Configuration changed; start a new job instead.",
                    409,
                )
            return self.submit(video, job.request.model_copy(update={"key": key}), job)

    def cancel(self, video: UUID, job_id: UUID) -> Job:
        with self.mutex:
            job = self.get(video, job_id)
            if job.status != "queued":
                raise ServiceError(
                    "job_not_queued", "Only queued jobs can be cancelled.", 409
                )
            job.status = "cancelled"
            self._save(job)
            with self.activity.lock:
                self.activity.active -= 1
            return job

    def checkpoint(self, job: Job, stage: str, run_id: UUID | None = None) -> None:
        with self.mutex:
            job.stage = stage
            if run_id is not None:
                job.outputs[stage] = run_id
            self._save(job)

    def _loop(self) -> None:
        try:
            while not self.stop.is_set():
                with self.mutex:
                    job = next((j for j in self._all() if j.status == "queued"), None)
                    if job:
                        job.status = "running"
                        self._save(job)
                if job is None:
                    self.wake.wait(0.5)
                    self.wake.clear()
                    continue
                try:
                    if job.configuration != self.configuration:
                        raise ServiceError(
                            "job_configuration_changed",
                            "Configuration changed; start a new job.",
                            409,
                        )
                    self.execute(job, self.checkpoint)
                    job.status = (
                        "needs_review"
                        if job.request.action == "analyze"
                        else "completed"
                    )
                except ServiceError as exc:
                    job.status = "failed"
                    job.error_code = exc.code
                except Exception:
                    job.status = "failed"
                    job.error_code = "job_processing_failed"
                finally:
                    try:
                        with self.mutex:
                            self._save(job)
                    finally:
                        with self.activity.lock:
                            self.activity.active -= 1
                    logging.getLogger("verifistream").info(
                        json.dumps(
                            {
                                "event": "job_finished",
                                "id": str(job.id),
                                "status": job.status,
                            }
                        )
                    )
        finally:
            self.ready = False
            # No pending reservations survive this worker lifetime.
            with self.mutex:
                pending = sum(j.status == "queued" for j in self._all())
                with self.activity.lock:
                    self.activity.active -= pending
            if self.file:
                self.file.close()
