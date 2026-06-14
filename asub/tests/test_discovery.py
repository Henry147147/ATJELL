from pathlib import Path

from asub.discovery import discover_inputs


def test_discover_single_multi_folder_and_glob(tmp_path):
    one = tmp_path / "video one.mp4"
    two = tmp_path / "unicodé.mkv"
    ignored = tmp_path / "notes.txt"
    sub = tmp_path / "folder"
    sub.mkdir()
    three = sub / "clip.mov"
    for path in [one, two, ignored, three]:
        path.write_text("x", encoding="utf-8")

    found = discover_inputs([one, tmp_path / "*.mkv", sub])
    assert found == sorted([one.resolve(), two.resolve(), three.resolve()], key=lambda p: str(p).casefold())


def test_discovery_ignores_unsupported(tmp_path):
    bad = tmp_path / "audio.mp3"
    bad.write_text("x", encoding="utf-8")
    assert discover_inputs([tmp_path]) == []
