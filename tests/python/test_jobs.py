from pathlib import Path

from asub_service.config import ServiceConfig
from asub_service.jobs import JobRequest, JobStatus, SubtitleJobQueue


class FakeRunner:
    def __init__(self):
        self.calls = []
        self.unloaded = 0

    async def run(self, request, config):
        self.calls.append((request, config))
        return [Path(request.media_path).with_suffix(".en.srt")]

    async def unload(self):
        self.unloaded += 1


def test_queue_runs_job_and_unloads_when_idle(tmp_path):
    runner = FakeRunner()
    queue = SubtitleJobQueue(ServiceConfig(), runner=runner)
    media = tmp_path / "Movie.mkv"
    media.write_text("media", encoding="utf-8")

    job = queue.enqueue(JobRequest(media_path=media, target_languages=["en"], existing_languages=[]))
    queue.run_until_idle()

    status = queue.status(job.id)
    assert status.state == JobStatus.COMPLETED
    assert status.outputs == [media.with_suffix(".en.srt")]
    assert runner.unloaded == 1


def test_queue_rejects_duplicate_active_media_job(tmp_path):
    runner = FakeRunner()
    queue = SubtitleJobQueue(ServiceConfig(), runner=runner)
    media = tmp_path / "Movie.mkv"
    media.write_text("media", encoding="utf-8")

    first = queue.enqueue(JobRequest(media_path=media, target_languages=["en"], existing_languages=[]))
    second = queue.enqueue(JobRequest(media_path=media, target_languages=["es"], existing_languages=[]))

    assert second.id == first.id
    assert len(queue.all_jobs()) == 1
