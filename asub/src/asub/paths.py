from __future__ import annotations

import re
from pathlib import Path

RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def normalize_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def safe_stem(path: Path) -> str:
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", path.stem).strip(" .")
    if not stem:
        stem = "video"
    if stem.upper() in RESERVED:
        stem = f"{stem}_video"
    return stem[:120]


def unique_dir(base: Path, stem: str) -> Path:
    candidate = base / stem
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = base / f"{stem}_{index}"
        if not candidate.exists():
            return candidate
        index += 1
