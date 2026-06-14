from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .exceptions import MediaError, ToolMissingError

MP4_LANGUAGE_TAGS = {
    "ar": "ara",
    "bn": "ben",
    "bo": "bod",
    "cs": "ces",
    "de": "deu",
    "en": "eng",
    "es": "spa",
    "fa": "fas",
    "fr": "fra",
    "gu": "guj",
    "he": "heb",
    "hi": "hin",
    "id": "ind",
    "it": "ita",
    "ja": "jpn",
    "kk": "kaz",
    "km": "khm",
    "ko": "kor",
    "mn": "mon",
    "mr": "mar",
    "ms": "msa",
    "my": "mya",
    "nl": "nld",
    "pl": "pol",
    "pt": "por",
    "ru": "rus",
    "ta": "tam",
    "te": "tel",
    "th": "tha",
    "tl": "tgl",
    "tr": "tur",
    "ug": "uig",
    "uk": "ukr",
    "ur": "urd",
    "vi": "vie",
    "yue": "yue",
    "zh": "zho",
    "zh-Hant": "zho",
}


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise ToolMissingError(f"Missing required tool: {name}. Install ffmpeg and ensure it is on PATH.")
    return path


def run_command(args: list[str], *, timeout: int | None = None, log: Any = None) -> subprocess.CompletedProcess[str]:
    if log:
        log.info("Running command: %s", " ".join(args))
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)
    except OSError as exc:
        raise MediaError(str(exc)) from exc
    if result.returncode != 0:
        raise MediaError(result.stderr.strip() or f"Command failed with exit code {result.returncode}: {args[0]}")
    return result


def ffprobe_json(video: Path, *, log: Any = None) -> dict[str, Any]:
    exe = require_tool("ffprobe")
    result = run_command(
        [
            exe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(video),
        ],
        log=log,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaError(f"ffprobe returned invalid JSON for {video}") from exc


def media_duration_seconds(probe: dict[str, Any]) -> float | None:
    duration = probe.get("format", {}).get("duration")
    if duration is None:
        return None
    try:
        return float(duration)
    except (TypeError, ValueError):
        return None


def extract_audio(video: Path, output_wav: Path, *, sample_rate: int = 24000, overwrite: bool = False, log: Any = None) -> Path:
    exe = require_tool("ffmpeg")
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    args = [exe, "-hide_banner", "-y" if overwrite else "-n", "-i", str(video), "-vn", "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(output_wav)]
    run_command(args, log=log)
    return output_wav


def extract_audio_chunk(source_wav: Path, chunk_wav: Path, *, start: float, duration: float, overwrite: bool = True, log: Any = None) -> Path:
    exe = require_tool("ffmpeg")
    chunk_wav.parent.mkdir(parents=True, exist_ok=True)
    args = [
        exe,
        "-hide_banner",
        "-y" if overwrite else "-n",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(source_wav),
        "-c:a",
        "pcm_s16le",
        str(chunk_wav),
    ]
    run_command(args, log=log)
    return chunk_wav


def _mp4_language_tag(language: str) -> str:
    return MP4_LANGUAGE_TAGS.get(language, language)


def build_mux_command(video: Path, subtitle_files: list[tuple[Path, str]], output: Path, *, overwrite: bool = False) -> list[str]:
    exe = require_tool("ffmpeg")
    args = [exe, "-hide_banner", "-y" if overwrite else "-n", "-i", str(video)]
    for subtitle, _lang in subtitle_files:
        args.extend(["-i", str(subtitle)])
    if output.suffix.lower() in {".mp4", ".m4v"}:
        args.extend(["-map", "0:v?", "-map", "0:a?"])
        for idx, _subtitle in enumerate(subtitle_files, start=1):
            args.extend(["-map", f"{idx}:0"])
        args.extend(["-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text"])
    else:
        args.extend(["-map", "0", "-c", "copy"])
    is_mp4 = output.suffix.lower() in {".mp4", ".m4v"}
    for idx, (_subtitle, lang) in enumerate(subtitle_files):
        metadata_language = _mp4_language_tag(lang) if is_mp4 else lang
        if not is_mp4:
            out_idx = idx + 1
            args.extend(["-map", str(out_idx)])
        args.extend([f"-metadata:s:s:{idx}", f"language={metadata_language}", f"-metadata:s:s:{idx}", f"title={lang}"])
    if is_mp4:
        args.extend(["-movflags", "+faststart"])
    args.append(str(output))
    return args


def mux_subtitles(video: Path, subtitle_files: list[tuple[Path, str]], output: Path, *, overwrite: bool = False, log: Any = None) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    run_command(build_mux_command(video, subtitle_files, output, overwrite=overwrite), log=log)
    return output


def _ffmpeg_filter_path(path: Path) -> str:
    # ffmpeg/libass accepts forward slashes and needs escaped drive separators.
    text = str(path.resolve(strict=False)).replace("\\", "/")
    return text.replace(":", r"\:")


def build_burn_command(video: Path, ass_file: Path, output: Path, *, encoder: str = "hevc_nvenc", preset: str = "p5", cq: int = 22, overwrite: bool = False) -> list[str]:
    exe = require_tool("ffmpeg")
    return [
        exe,
        "-hide_banner",
        "-y" if overwrite else "-n",
        "-i",
        str(video),
        "-vf",
        f"ass='{_ffmpeg_filter_path(ass_file)}'",
        "-c:v",
        encoder,
        "-preset",
        preset,
        "-cq",
        str(cq),
        "-c:a",
        "copy",
        str(output),
    ]


def burn_subtitles(video: Path, ass_file: Path, output: Path, *, encoder: str = "hevc_nvenc", preset: str = "p5", cq: int = 22, overwrite: bool = False, log: Any = None) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    run_command(build_burn_command(video, ass_file, output, encoder=encoder, preset=preset, cq=cq, overwrite=overwrite), log=log)
    return output
