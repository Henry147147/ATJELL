from pathlib import Path

from asub_service.sidecars import build_sidecar_paths, missing_languages


def test_build_sidecar_paths_use_jellyfin_language_suffix(tmp_path):
    video = tmp_path / "Series Name S01E01.mkv"

    paths = build_sidecar_paths(video, ["en", "es"], ["srt", "vtt"])

    assert paths == [
        tmp_path / "Series Name S01E01.en.srt",
        tmp_path / "Series Name S01E01.en.vtt",
        tmp_path / "Series Name S01E01.es.srt",
        tmp_path / "Series Name S01E01.es.vtt",
    ]


def test_missing_languages_accept_embedded_and_sidecar_languages(tmp_path):
    video = tmp_path / "Movie.mkv"
    (tmp_path / "Movie.es.srt").write_text("1\n", encoding="utf-8")

    assert missing_languages(video, ["en", "es"], existing_languages=["en"], formats=["srt"]) == []
    assert missing_languages(video, ["en", "es"], existing_languages=[], formats=["srt"]) == ["en"]
