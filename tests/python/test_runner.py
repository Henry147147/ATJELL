from pathlib import Path

from asub_service.config import ServiceConfig
from asub_service.jobs import JobRequest
from asub_service.runner import AsubPipelineRunner


def test_runner_invokes_asub_with_sidecar_only_options(monkeypatch, tmp_path):
    media = tmp_path / "Movie.mkv"
    media.write_text("media", encoding="utf-8")
    generated = tmp_path / "work" / "Movie.es.srt"
    generated.parent.mkdir()
    generated.write_text("subtitle", encoding="utf-8")
    captured = {}

    class FakeJob:
        generated_files = {"es.srt": str(generated), "mux.mp4": str(tmp_path / "bad.mp4")}

    class FakePipeline:
        def __init__(self, options):
            captured["options"] = options

        def process_video(self, video):
            captured["video"] = video
            return FakeJob()

    monkeypatch.setattr("asub_service.runner.Pipeline", FakePipeline)

    runner = AsubPipelineRunner()
    outputs = runner.run_sync(
        JobRequest(media_path=media, target_languages=["es"], existing_languages=[]),
        ServiceConfig(subtitle_formats=["srt"]),
    )

    assert captured["video"] == media
    assert captured["options"].mux is False
    assert captured["options"].burn is False
    assert captured["options"].in_place is False
    assert captured["options"].target_languages == ["es"]
    assert outputs == [tmp_path / "Movie.es.srt"]
    assert outputs[0].read_text(encoding="utf-8") == "subtitle"
    assert not (tmp_path / "bad.mp4").exists()


def test_runner_skips_languages_that_are_no_longer_missing(monkeypatch, tmp_path):
    media = tmp_path / "Movie.mkv"
    media.write_text("media", encoding="utf-8")
    (tmp_path / "Movie.en.srt").write_text("existing", encoding="utf-8")

    class FailingPipeline:
        def __init__(self, options):
            raise AssertionError("pipeline should not run")

    monkeypatch.setattr("asub_service.runner.Pipeline", FailingPipeline)

    runner = AsubPipelineRunner()
    outputs = runner.run_sync(
        JobRequest(media_path=media, target_languages=["en"], existing_languages=[]),
        ServiceConfig(subtitle_formats=["srt"]),
    )

    assert outputs == []
