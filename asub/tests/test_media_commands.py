from pathlib import Path

from asub import media


def test_mux_command_uses_argument_array(monkeypatch, tmp_path):
    monkeypatch.setattr(media, "require_tool", lambda name: f"C:/bin/{name}.exe")
    video = tmp_path / "video file.mkv"
    sub = tmp_path / "sub title.srt"
    cmd = media.build_mux_command(video, [(sub, "en")], tmp_path / "out.mkv", overwrite=True)
    assert cmd[0].endswith("ffmpeg.exe")
    assert str(video) in cmd
    assert str(sub) in cmd
    assert "language=en" in cmd


def test_burn_command_uses_nvenc_options(monkeypatch, tmp_path):
    monkeypatch.setattr(media, "require_tool", lambda name: f"C:/bin/{name}.exe")
    cmd = media.build_burn_command(tmp_path / "v.mkv", tmp_path / "s.ass", tmp_path / "out.mkv", encoder="h264_nvenc", preset="p4", cq=20)
    assert "-c:v" in cmd
    assert "h264_nvenc" in cmd
    assert "-cq" in cmd
    assert "20" in cmd
