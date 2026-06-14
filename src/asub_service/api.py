from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from .config import ServiceConfig
from .jobs import JobRequest, SubtitleJobQueue
from .runner import AsubPipelineRunner


class CreateJobBody(BaseModel):
    media_path: Path
    target_languages: list[str] = Field(default_factory=list)
    existing_languages: list[str] = Field(default_factory=list)


def create_app(config: ServiceConfig | None = None, *, runner=None) -> FastAPI:
    service_config = config or ServiceConfig.from_env()
    queue = SubtitleJobQueue(service_config, runner=runner or AsubPipelineRunner())
    app = FastAPI(title="Auto Transcription ASR Service")

    def authorize(authorization: str | None = Header(default=None)) -> None:
        if not service_config.api_token:
            return
        expected = f"Bearer {service_config.api_token}"
        if authorization != expected:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/jobs", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(authorize)])
    async def create_job(body: CreateJobBody) -> dict[str, object]:
        targets = body.target_languages or service_config.target_languages
        record = queue.enqueue(
            JobRequest(
                media_path=body.media_path,
                target_languages=targets,
                existing_languages=body.existing_languages,
            )
        )
        await queue.drain()
        return _record(record)

    @app.get("/v1/jobs/{job_id}", dependencies=[Depends(authorize)])
    def get_job(job_id: str) -> dict[str, object]:
        try:
            record = queue.status(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
        return _record(record)

    return app


def _record(record) -> dict[str, object]:
    return {
        "id": record.id,
        "state": record.state.value,
        "media_path": str(record.request.media_path),
        "target_languages": record.request.target_languages,
        "outputs": [str(path) for path in record.outputs],
        "error": record.error,
    }


app = create_app()
