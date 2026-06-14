from __future__ import annotations

from pathlib import Path

from asub.languages import parse_targets


def build_sidecar_paths(video: Path, languages: list[str], formats: list[str]) -> list[Path]:
    normalized_languages = parse_targets(languages)
    normalized_formats = [fmt.strip().lower().lstrip(".") for fmt in formats if fmt.strip()]
    return [
        video.with_name(f"{video.stem}.{language}.{fmt}")
        for language in normalized_languages
        for fmt in normalized_formats
    ]


def sidecar_exists(video: Path, language: str, formats: list[str]) -> bool:
    return any(path.exists() for path in build_sidecar_paths(video, [language], formats))


def missing_languages(
    video: Path,
    target_languages: list[str],
    *,
    existing_languages: list[str],
    formats: list[str],
) -> list[str]:
    present = {lang.casefold() for lang in parse_targets(existing_languages)}
    missing: list[str] = []
    for language in parse_targets(target_languages):
        if language.casefold() in present:
            continue
        if sidecar_exists(video, language, formats):
            continue
        missing.append(language)
    return missing
