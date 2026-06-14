from __future__ import annotations

import glob
from pathlib import Path

from .paths import normalize_path

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}


def _has_glob_magic(value: str) -> bool:
    return any(ch in value for ch in "*?[")


def discover_inputs(inputs: list[str | Path], *, recursive_folders: bool = True) -> list[Path]:
    discovered: list[Path] = []
    for raw in inputs:
        text = str(raw)
        if _has_glob_magic(text):
            for match in glob.glob(text, recursive=True):
                path = normalize_path(match)
                if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
                    discovered.append(path)
            continue

        path = normalize_path(text)
        if path.is_dir():
            iterator = path.rglob("*") if recursive_folders else path.glob("*")
            discovered.extend(p for p in iterator if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS)
        elif path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            discovered.append(path)

    deduped: list[Path] = []
    seen: set[str] = set()
    for path in discovered:
        key = str(path).casefold()
        if key not in seen:
            seen.add(key)
            deduped.append(path)
    return sorted(deduped, key=lambda p: str(p).casefold())
