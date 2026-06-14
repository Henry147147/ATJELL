import shutil
from pathlib import Path

import pytest

from asub.media import ffprobe_json, media_duration_seconds, run_command


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ffmpeg/ffprobe not available")
def test_generated_dummy_media_can_be_probed(tmp_path):
    video = tmp_path / "dummy.mp4"
    run_command(
        [
            shutil.which("ffmpeg"),
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=64x64:rate=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=44100",
            "-t",
            "1",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ]
    )
    probe = ffprobe_json(video)
    assert media_duration_seconds(probe) is not None


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ffmpeg/ffprobe not available")
def test_five_minute_fixture_can_be_remuxed_with_subtitles(tmp_path):
    fixture = Path("tests/fixtures/caso_cerrado_5min.mp4")
    if not fixture.exists():
        pytest.skip("local fixture not created")

    probe = ffprobe_json(fixture)
    duration = media_duration_seconds(probe)
    assert duration is not None
    assert 295 <= duration <= 305

    subtitle = tmp_path / "caption.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nhello\n", encoding="utf-8")
    output = tmp_path / "remuxed.mkv"
    run_command(
        [
            shutil.which("ffmpeg"),
            "-hide_banner",
            "-y",
            "-i",
            str(fixture),
            "-i",
            str(subtitle),
            "-map",
            "0",
            "-map",
            "1",
            "-c",
            "copy",
            "-metadata:s:s:0",
            "language=en",
            str(output),
        ]
    )
    remux_probe = ffprobe_json(output)
    assert any(stream.get("codec_type") == "subtitle" for stream in remux_probe["streams"])
