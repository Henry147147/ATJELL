from __future__ import annotations

import html
import re
from pathlib import Path

from .exceptions import MediaError
from .models import CaptionSegment, ProcessingOptions


def validate_segments(segments: list[CaptionSegment]) -> None:
    previous_end = -1.0
    for segment in segments:
        if segment.start < 0 or segment.end < 0 or segment.end <= segment.start:
            raise MediaError(f"Invalid subtitle timing at segment {segment.index}: {segment.start} -> {segment.end}")
        if segment.start < previous_end - 0.05:
            raise MediaError(f"Overlapping subtitle timing at segment {segment.index}")
        previous_end = segment.end


def _srt_time(seconds: float) -> str:
    ms = round(seconds * 1000)
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _vtt_time(seconds: float) -> str:
    return _srt_time(seconds).replace(",", ".")


def _ass_time(seconds: float) -> str:
    cs = round(seconds * 100)
    hours, rem = divmod(cs, 360_000)
    minutes, rem = divmod(rem, 6_000)
    secs, centis = divmod(rem, 100)
    return f"{hours}:{minutes:02}:{secs:02}.{centis:02}"


def wrap_text(text: str, *, width: int = 42, max_lines: int = 2) -> str:
    words = text.split()
    if not words:
        return ""
    lines: list[str] = []
    current = ""
    for word in words:
        next_line = word if not current else f"{current} {word}"
        if len(next_line) <= width:
            current = next_line
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) <= max_lines:
        return "\n".join(lines)
    split = max(1, min(len(words) - 1, len(words) // 2))
    return " ".join(words[:split]) + "\n" + " ".join(words[split:])


def _visible(segment: CaptionSegment, options: ProcessingOptions) -> str:
    return wrap_text(segment.display_text(options.speaker_labels), width=options.max_subtitle_chars)


def render_srt(segments: list[CaptionSegment], options: ProcessingOptions) -> str:
    validate_segments(segments)
    blocks = []
    for out_index, segment in enumerate(segments, start=1):
        blocks.append(f"{out_index}\n{_srt_time(segment.start)} --> {_srt_time(segment.end)}\n{_visible(segment, options)}")
    return "\n\n".join(blocks) + "\n"


def render_vtt(segments: list[CaptionSegment], options: ProcessingOptions) -> str:
    validate_segments(segments)
    blocks = ["WEBVTT\n"]
    for segment in segments:
        blocks.append(f"{_vtt_time(segment.start)} --> {_vtt_time(segment.end)}\n{_visible(segment, options)}")
    return "\n\n".join(blocks) + "\n"


def _ass_escape(text: str) -> str:
    text = text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
    return text.replace("\n", r"\N")


def render_ass(segments: list[CaptionSegment], options: ProcessingOptions) -> str:
    validate_segments(segments)
    header = f"""[Script Info]
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{options.ass_font},{options.ass_font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,{options.ass_outline},{options.ass_shadow},2,64,64,{options.ass_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for segment in segments:
        text = _ass_escape(_visible(segment, options))
        lines.append(f"Dialogue: 0,{_ass_time(segment.start)},{_ass_time(segment.end)},Default,,0,0,0,,{text}")
    return header + "\n".join(lines) + "\n"


def write_subtitles(segments: list[CaptionSegment], directory: Path, basename: str, language: str, options: ProcessingOptions) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}
    formats = {fmt.lower().strip(".") for fmt in options.formats}
    if options.burn:
        formats.add("ass")
    if "srt" in formats:
        path = directory / f"{basename}.{language}.srt"
        path.write_text(render_srt(segments, options), encoding="utf-8")
        outputs["srt"] = path
    if "vtt" in formats:
        path = directory / f"{basename}.{language}.vtt"
        path.write_text(render_vtt(segments, options), encoding="utf-8")
        outputs["vtt"] = path
    if "ass" in formats:
        path = directory / f"{basename}.{language}.ass"
        path.write_text(render_ass(segments, options), encoding="utf-8")
        outputs["ass"] = path
    return outputs


def parse_srt(path: Path) -> list[CaptionSegment]:
    text = path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"\n\s*\n", text.strip())
    segments: list[CaptionSegment] = []
    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        timing = lines[1]
        start, end = [part.strip() for part in timing.split("-->")[:2]]
        segments.append(CaptionSegment(index=len(segments) + 1, start=_parse_srt_time(start), end=_parse_srt_time(end), text=html.unescape(" ".join(lines[2:]))))
    return segments


def _parse_srt_time(value: str) -> float:
    hms, ms = value.replace(".", ",").split(",")
    h, m, s = [int(part) for part in hms.split(":")]
    return h * 3600 + m * 60 + s + int(ms[:3].ljust(3, "0")) / 1000
