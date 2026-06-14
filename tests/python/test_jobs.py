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


def test_queue_runs_concurrent_drains_up_to_configured_stage_limit(tmp_path):
    import asyncio

    class CoordinatedRunner:
        def __init__(self):
            import asyncio

            self.active = 0
            self.max_active = 0
            self.unloaded = 0
            self.first_started = asyncio.Event()
            self.second_started = asyncio.Event()
            self.release = asyncio.Event()

        async def run(self, request, config):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            if self.active == 1:
                self.first_started.set()
            if self.active == 2:
                self.second_started.set()
            await self.release.wait()
            self.active -= 1
            return [Path(request.media_path).with_suffix(".en.srt")]

        async def unload(self):
            self.unloaded += 1

    async def exercise():
        runner = CoordinatedRunner()
        queue = SubtitleJobQueue(
            ServiceConfig(max_concurrent_asr=1, max_concurrent_alignment=2, max_concurrent_translation=2),
            runner=runner,
        )
        first = tmp_path / "First.mkv"
        second = tmp_path / "Second.mkv"
        first.write_text("media", encoding="utf-8")
        second.write_text("media", encoding="utf-8")

        queue.enqueue(JobRequest(media_path=first, target_languages=["en"], existing_languages=[]))
        first_drain = asyncio.create_task(queue.drain())
        await asyncio.wait_for(runner.first_started.wait(), timeout=1)

        queue.enqueue(JobRequest(media_path=second, target_languages=["en"], existing_languages=[]))
        second_drain = asyncio.create_task(queue.drain())
        await asyncio.wait_for(runner.second_started.wait(), timeout=1)

        runner.release.set()
        await asyncio.gather(first_drain, second_drain)

        assert runner.max_active == 2
        assert runner.unloaded == 1

    asyncio.run(exercise())
