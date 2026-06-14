from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from .config import ServiceConfig


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class JobRequest:
    media_path: Path
    target_languages: list[str]
    existing_languages: list[str] = field(default_factory=list)


@dataclass
class JobRecord:
    id: str
    request: JobRequest
    state: JobStatus = JobStatus.QUEUED
    outputs: list[Path] = field(default_factory=list)
    error: str | None = None


class JobRunner(Protocol):
    async def run(self, request: JobRequest, config: ServiceConfig) -> list[Path]:
        ...

    async def unload(self) -> None:
        ...


class SubtitleJobQueue:
    def __init__(self, config: ServiceConfig, *, runner: JobRunner):
        self._config = config
        self._runner = runner
        self._jobs: dict[str, JobRecord] = {}
        self._active_by_media: dict[Path, str] = {}
        self._run_semaphore = asyncio.Semaphore(
            max(
                1,
                config.max_concurrent_asr,
                config.max_concurrent_alignment,
                config.max_concurrent_translation,
            )
        )
        self._unload_lock = asyncio.Lock()
        self._unloaded_after_idle = False

    def enqueue(self, request: JobRequest) -> JobRecord:
        media_path = request.media_path.resolve(strict=False)
        active_id = self._active_by_media.get(media_path)
        if active_id is not None:
            return self._jobs[active_id]
        normalized = JobRequest(media_path=media_path, target_languages=request.target_languages, existing_languages=request.existing_languages)
        record = JobRecord(id=str(uuid.uuid4()), request=normalized)
        self._jobs[record.id] = record
        self._active_by_media[media_path] = record.id
        self._unloaded_after_idle = False
        return record

    def status(self, job_id: str) -> JobRecord:
        return self._jobs[job_id]

    def all_jobs(self) -> list[JobRecord]:
        return list(self._jobs.values())

    async def drain(self) -> None:
        for record in list(self._jobs.values()):
            if record.state != JobStatus.QUEUED:
                continue
            record.state = JobStatus.RUNNING
            try:
                async with self._run_semaphore:
                    record.outputs = await self._runner.run(record.request, self._config)
                record.state = JobStatus.COMPLETED
            except Exception as exc:
                record.error = str(exc)
                record.state = JobStatus.FAILED
            finally:
                self._active_by_media.pop(record.request.media_path, None)
        await self._unload_when_idle()

    async def _unload_when_idle(self) -> None:
        if not self._config.unload_on_idle:
            return
        async with self._unload_lock:
            if self._unloaded_after_idle:
                return
            if any(record.state in {JobStatus.QUEUED, JobStatus.RUNNING} for record in self._jobs.values()):
                return
            await self._runner.unload()
            self._unloaded_after_idle = True

    def run_until_idle(self) -> None:
        asyncio.run(self.drain())
