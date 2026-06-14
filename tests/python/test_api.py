from pathlib import Path

from fastapi.testclient import TestClient

from asub_service.api import create_app
from asub_service.config import ServiceConfig


class FakeRunner:
    async def run(self, request, config):
        return [Path(request.media_path).with_suffix(".en.srt")]

    async def unload(self):
        return None


def test_api_accepts_job_and_returns_completed_status(tmp_path):
    media = tmp_path / "Movie.mkv"
    media.write_text("media", encoding="utf-8")
    app = create_app(ServiceConfig(api_token="secret"), runner=FakeRunner())
    client = TestClient(app)

    created = client.post(
        "/v1/jobs",
        headers={"Authorization": "Bearer secret"},
        json={"media_path": str(media), "target_languages": ["en"], "existing_languages": []},
    )

    assert created.status_code == 202
    job_id = created.json()["id"]

    status = client.get(f"/v1/jobs/{job_id}", headers={"Authorization": "Bearer secret"})
    assert status.status_code == 200
    assert status.json()["state"] == "completed"
    assert status.json()["outputs"] == [str(media.with_suffix(".en.srt"))]


def test_health_does_not_require_token():
    app = create_app(ServiceConfig(api_token="secret"), runner=FakeRunner())
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200


def test_api_rejects_invalid_token(tmp_path):
    media = tmp_path / "Movie.mkv"
    media.write_text("media", encoding="utf-8")
    app = create_app(ServiceConfig(api_token="secret"), runner=FakeRunner())
    client = TestClient(app)

    response = client.post(
        "/v1/jobs",
        headers={"Authorization": "Bearer wrong"},
        json={"media_path": str(media), "target_languages": ["en"], "existing_languages": []},
    )

    assert response.status_code == 401
