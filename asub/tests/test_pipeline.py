from pathlib import Path
import errno
import time

import pytest

from asub import media
from asub.exceptions import WorkerError
from asub.models import ProcessingOptions
from asub.orchestrator import Pipeline, translate_existing, _replace_file


class FakeAsr:
    def call(self, payload, timeout=None):
        return {
            "ok": True,
            "detected_language": "en",
            "segments": [
                {"index": 1, "start": 0.0, "end": 1.2, "text": "Hello", "speaker": "Speaker 1"},
                {"index": 2, "start": 1.4, "end": 2.5, "text": "World", "speaker": "Speaker 2"},
            ],
        }


class FakeMt:
    def call(self, payload, timeout=None):
        target = payload["target_language"]
        segs = []
        for seg in payload["segments"]:
            item = dict(seg)
            item["text"] = f"{seg['text']} [{target}]"
            segs.append(item)
        return {"ok": True, "segments": segs}


class FakeAlign:
    def call(self, payload, timeout=None):
        segs = []
        for seg in payload["segments"]:
            item = dict(seg)
            item["aligned_start"] = seg["start"] + 0.1
            item["aligned_end"] = seg["end"] - 0.1
            item["start"] = item["aligned_start"]
            item["end"] = item["aligned_end"]
            item["words"] = [{"text": item["text"], "start": item["start"], "end": item["end"]}]
            segs.append(item)
        return {"ok": True, "segments": segs}


class ClosableFakeAsr(FakeAsr):
    def __init__(self, events):
        self.events = events

    def call(self, payload, timeout=None):
        self.events.append("asr")
        return super().call(payload, timeout)

    def close(self):
        self.events.append("close_asr")


def patch_media(monkeypatch):
    monkeypatch.setattr(media, "ffprobe_json", lambda video, log=None: {"format": {"duration": "10"}})

    def fake_extract(video, out, sample_rate=24000, overwrite=False, log=None):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"wav")
        return out

    monkeypatch.setattr(media, "extract_audio", fake_extract)
    monkeypatch.setattr(media, "mux_subtitles", lambda video, tracks, output, overwrite=False, log=None: output.write_text("mux") or output)
    monkeypatch.setattr(media, "burn_subtitles", lambda video, ass, output, encoder="hevc_nvenc", preset="p5", cq=22, overwrite=False, log=None: output.write_text("burn") or output)


def test_replace_file_handles_cross_device_replacement(monkeypatch, tmp_path):
    source = tmp_path / "source.mp4"
    target = tmp_path / "target.mp4"
    source.write_text("new", encoding="utf-8")
    target.write_text("old", encoding="utf-8")
    original_replace = Path.replace

    def fake_replace(self, replacement):
        if self == source:
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        return original_replace(self, replacement)

    monkeypatch.setattr(Path, "replace", fake_replace)

    _replace_file(source, target)

    assert target.read_text(encoding="utf-8") == "new"
    assert not source.exists()


def test_pipeline_processes_video_with_translation_alignment_mux_burn(monkeypatch, tmp_path):
    patch_media(monkeypatch)
    video = tmp_path / "Input Vidéo.mkv"
    video.write_text("x", encoding="utf-8")
    options = ProcessingOptions(output_dir=tmp_path / "out", target_languages=["en", "es"], align=True, mux=True, burn=True, formats=["srt", "vtt", "ass"])
    job = Pipeline(options, asr_client=FakeAsr(), mt_client=FakeMt(), align_client=FakeAlign()).process_video(video)
    assert job.status["job"] == "completed"
    assert job.translations["en"][0].text == "Hello"
    assert job.translations["es"][0].text == "Hello [es]"
    assert Path(job.generated_files["es.srt"]).exists()
    assert Path(job.generated_files["mux.mp4"]).exists()
    assert job.generated_files["burn.es"]


def test_pipeline_uses_configured_asr_model(monkeypatch, tmp_path):
    patch_media(monkeypatch)
    video = tmp_path / "v.mkv"
    video.write_text("x", encoding="utf-8")

    class CapturingAsr(FakeAsr):
        seen_model = None

        def call(self, payload, timeout=None):
            self.seen_model = payload["model"]
            return super().call(payload, timeout)

    asr = CapturingAsr()
    options = ProcessingOptions(output_dir=tmp_path / "out", asr_model="custom/asr-model")
    Pipeline(options, asr_client=asr, mt_client=FakeMt(), align_client=FakeAlign()).process_video(video)
    assert asr.seen_model == "custom/asr-model"


def test_pipeline_defaults_to_qwen_mux_and_no_burn():
    options = ProcessingOptions()
    pipeline = Pipeline(options, mt_client=FakeMt(), align_client=FakeAlign())
    assert options.asr_model == "Qwen/Qwen3-ASR-1.7B"
    assert options.asr_max_model_len == 16384
    assert options.asr_gpu_memory_utilization == 0.65
    assert options.mux is True
    assert options.burn is False
    assert pipeline.asr_client.kind == "qwen_asr"
    assert pipeline.asr_client.module == "asub.workers.qwen_asr_worker"


def test_pipeline_default_mux_does_not_burn(monkeypatch, tmp_path):
    patch_media(monkeypatch)
    video = tmp_path / "v.mkv"
    video.write_text("x", encoding="utf-8")
    burn_calls = []
    monkeypatch.setattr(media, "burn_subtitles", lambda *args, **kwargs: burn_calls.append(args))

    job = Pipeline(
        ProcessingOptions(output_dir=tmp_path / "out"),
        asr_client=FakeAsr(),
        mt_client=FakeMt(),
        align_client=FakeAlign(),
    ).process_video(video)

    assert Path(job.generated_files["mux.mp4"]).exists()
    assert Path(job.generated_files["mux.mp4"]).suffix == ".mp4"
    assert not any(key.startswith("burn.") for key in job.generated_files)
    assert burn_calls == []


def test_in_place_cleanup_overwrites_single_mp4_and_removes_job_dir(monkeypatch, tmp_path):
    patch_media(monkeypatch)
    video = tmp_path / "v.mp4"
    video.write_text("original", encoding="utf-8")

    job = Pipeline(
        ProcessingOptions(output_dir=tmp_path / "out", in_place=True, cleanup=True),
        asr_client=FakeAsr(),
        mt_client=FakeMt(),
        align_client=FakeAlign(),
    ).process_video(video)

    assert video.read_text(encoding="utf-8") == "mux"
    assert job.generated_files["mux.mp4"] == str(video)
    assert job.status["in_place"] == "completed"
    assert not job.output_dir.exists()


def test_cleanup_without_in_place_removes_work_and_logs_but_keeps_outputs(monkeypatch, tmp_path):
    patch_media(monkeypatch)
    video = tmp_path / "v.mp4"
    video.write_text("original", encoding="utf-8")

    job = Pipeline(
        ProcessingOptions(output_dir=tmp_path / "out", cleanup=True),
        asr_client=FakeAsr(),
        mt_client=FakeMt(),
        align_client=FakeAlign(),
    ).process_video(video)

    assert Path(job.generated_files["mux.mp4"]).exists()
    assert job.output_dir.exists()
    assert not job.work_dir.exists()
    assert not job.log_path.parent.exists()
    assert job.metadata_path.exists()
    assert job.status["cleanup"] == "completed"


def test_in_place_directory_inputs_convert_to_mp4_and_cleanup_each_job(monkeypatch, tmp_path):
    patch_media(monkeypatch)
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    mkv = source_dir / "a.mkv"
    mp4 = source_dir / "b.mp4"
    mkv.write_text("mkv-original", encoding="utf-8")
    mp4.write_text("mp4-original", encoding="utf-8")

    jobs = Pipeline(
        ProcessingOptions(output_dir=tmp_path / "out", in_place=True, cleanup=True, jobs=2),
        asr_client=FakeAsr(),
        mt_client=FakeMt(),
        align_client=FakeAlign(),
    ).process_inputs([source_dir])

    converted = source_dir / "a.mp4"
    assert len(jobs) == 2
    assert not mkv.exists()
    assert converted.read_text(encoding="utf-8") == "mux"
    assert mp4.read_text(encoding="utf-8") == "mux"
    assert all(job.status["in_place"] == "completed" for job in jobs)
    assert all(not job.output_dir.exists() for job in jobs)


def test_process_inputs_runs_videos_concurrently(monkeypatch, tmp_path):
    patch_media(monkeypatch)
    videos = []
    for idx in range(2):
        video = tmp_path / f"v{idx}.mkv"
        video.write_text("x", encoding="utf-8")
        videos.append(video)

    class SlowAsr(FakeAsr):
        def call(self, payload, timeout=None):
            time.sleep(0.25)
            return super().call(payload, timeout)

    start = time.perf_counter()
    jobs = Pipeline(
        ProcessingOptions(output_dir=tmp_path / "out", jobs=2),
        asr_client=SlowAsr(),
        mt_client=FakeMt(),
        align_client=FakeAlign(),
    ).process_inputs(videos)
    elapsed = time.perf_counter() - start

    assert len(jobs) == 2
    assert all(job.status["job"] == "completed" for job in jobs)
    assert elapsed < 0.45


def test_pipeline_releases_persistent_asr_before_standalone_align(monkeypatch, tmp_path):
    patch_media(monkeypatch)
    video = tmp_path / "v.mkv"
    video.write_text("x", encoding="utf-8")
    events = []

    class TrackingAlign(FakeAlign):
        def call(self, payload, timeout=None):
            events.append("align")
            return super().call(payload, timeout)

    job = Pipeline(
        ProcessingOptions(output_dir=tmp_path / "out", align=True),
        asr_client=ClosableFakeAsr(events),
        mt_client=FakeMt(),
        align_client=TrackingAlign(),
    ).process_video(video)

    assert job.status["align"] == "completed"
    assert events[:3] == ["asr", "close_asr", "align"]


def test_pipeline_skips_standalone_align_when_asr_already_aligned(monkeypatch, tmp_path):
    patch_media(monkeypatch)
    video = tmp_path / "v.mkv"
    video.write_text("x", encoding="utf-8")

    class AlignedAsr(FakeAsr):
        def call(self, payload, timeout=None):
            return {
                "ok": True,
                "detected_language": "en",
                "segments": [
                    {
                        "index": 1,
                        "start": 0.0,
                        "end": 1.0,
                        "text": "Hello",
                        "words": [{"text": "Hello", "start": 0.0, "end": 1.0}],
                        "aligned_start": 0.0,
                        "aligned_end": 1.0,
                    }
                ],
            }

    class FailingAlign:
        def call(self, payload, timeout=None):
            raise AssertionError("standalone align should not run")

    job = Pipeline(
        ProcessingOptions(output_dir=tmp_path / "out", align=True),
        asr_client=AlignedAsr(),
        mt_client=FakeMt(),
        align_client=FailingAlign(),
    ).process_video(video)

    assert job.status["align"] == "completed"


def test_resume_skips_completed_asr(monkeypatch, tmp_path):
    patch_media(monkeypatch)
    video = tmp_path / "v.mkv"
    video.write_text("x", encoding="utf-8")
    options = ProcessingOptions(output_dir=tmp_path / "out")
    pipeline = Pipeline(options, asr_client=FakeAsr(), mt_client=FakeMt(), align_client=FakeAlign())
    first = pipeline.process_video(video)
    second = pipeline.process_video(video)
    assert second.status["asr"] == "completed"
    assert second.metadata_path == first.metadata_path


def test_pipeline_records_worker_failure(monkeypatch, tmp_path):
    patch_media(monkeypatch)
    video = tmp_path / "v.mkv"
    video.write_text("x", encoding="utf-8")

    class BadAsr:
        def call(self, payload, timeout=None):
            raise WorkerError("CUDA out of memory")

    with pytest.raises(WorkerError):
        Pipeline(ProcessingOptions(output_dir=tmp_path / "out"), asr_client=BadAsr(), mt_client=FakeMt(), align_client=FakeAlign()).process_video(video)


def test_resume_failed_job_clears_stale_errors(monkeypatch, tmp_path):
    patch_media(monkeypatch)
    video = tmp_path / "v.mkv"
    video.write_text("x", encoding="utf-8")

    class BadAsr:
        def call(self, payload, timeout=None):
            raise WorkerError("old failure")

    options = ProcessingOptions(output_dir=tmp_path / "out")
    with pytest.raises(WorkerError):
        Pipeline(options, asr_client=BadAsr(), mt_client=FakeMt(), align_client=FakeAlign()).process_video(video)

    recovered = Pipeline(options, asr_client=FakeAsr(), mt_client=FakeMt(), align_client=FakeAlign()).process_video(video)
    assert recovered.status["job"] == "completed"
    assert recovered.errors == []


def test_translate_existing_adds_new_targets_after_completed_job(monkeypatch, tmp_path):
    patch_media(monkeypatch)
    video = tmp_path / "v.mkv"
    video.write_text("x", encoding="utf-8")
    job = Pipeline(ProcessingOptions(output_dir=tmp_path / "out"), asr_client=FakeAsr(), mt_client=FakeMt(), align_client=FakeAlign()).process_video(video)

    class LocalPipeline(Pipeline):
        def __init__(self, options):
            super().__init__(options, asr_client=FakeAsr(), mt_client=FakeMt(), align_client=FakeAlign())

    monkeypatch.setattr("asub.orchestrator.Pipeline", LocalPipeline)
    updated = translate_existing(job.metadata_path, ["es"], ProcessingOptions(output_dir=tmp_path / "out"))
    assert "es" in updated.translations
    assert Path(updated.generated_files["es.srt"]).exists()
