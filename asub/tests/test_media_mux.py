from pathlib import Path

from asub import media


def test_mp4_mux_command_copies_audio_video_and_converts_text_subtitles(monkeypatch):
    monkeypatch.setattr(media, "require_tool", lambda name: "ffmpeg")

    command = media.build_mux_command(
        Path("input.mkv"),
        [(Path("subs.en.srt"), "en")],
        Path("output.mp4"),
        overwrite=True,
    )

    assert command[:5] == ["ffmpeg", "-hide_banner", "-y", "-i", "input.mkv"]
    assert "-map" in command
    assert ["-c:v", "copy"] == command[command.index("-c:v") : command.index("-c:v") + 2]
    assert ["-c:a", "copy"] == command[command.index("-c:a") : command.index("-c:a") + 2]
    assert ["-c:s", "mov_text"] == command[command.index("-c:s") : command.index("-c:s") + 2]
    assert "language=eng" in command
    assert "title=en" in command
    assert "-c" not in command
    assert command[-1] == "output.mp4"
