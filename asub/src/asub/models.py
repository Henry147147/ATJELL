from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Literal


def _dump(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {k: _dump(v) for k, v in asdict(value).items()}
    if isinstance(value, list):
        return [_dump(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _dump(v) for k, v in value.items()}
    return value


class ModelMixin:
    def model_dump(self) -> dict[str, Any]:
        return _dump(self)

    def model_dump_json(self, **kwargs: Any) -> str:
        return json.dumps(self.model_dump(), ensure_ascii=False, **kwargs)

    @classmethod
    def model_validate(cls, data: Any):
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise TypeError(f"Cannot validate {type(data)!r} as {cls.__name__}")
        return _construct(cls, data)

    @classmethod
    def model_validate_json(cls, payload: str):
        return cls.model_validate(json.loads(payload))


def _construct(cls: type, data: dict[str, Any]):
    kwargs: dict[str, Any] = {}
    for item in fields(cls):
        if item.name not in data:
            continue
        value = data[item.name]
        typ = item.type
        if typ is Path:
            value = Path(value)
        elif typ in (list["CaptionSegment"], "list[CaptionSegment]"):
            value = [CaptionSegment.model_validate(v) for v in value]
        elif typ in (list["WordTimestamp"], "list[WordTimestamp]"):
            value = [WordTimestamp.model_validate(v) for v in value]
        elif item.name == "segments":
            value = [CaptionSegment.model_validate(v) for v in value]
        kwargs[item.name] = value
    return cls(**kwargs)


@dataclass
class WordTimestamp(ModelMixin):
    text: str
    start: float
    end: float


@dataclass
class CaptionSegment(ModelMixin):
    index: int
    start: float
    end: float
    text: str
    speaker: str | None = None
    words: list[WordTimestamp] = field(default_factory=list)
    asr_start: float | None = None
    asr_end: float | None = None
    aligned_start: float | None = None
    aligned_end: float | None = None

    def display_text(self, speaker_labels: Literal["visible", "hidden"] = "visible") -> str:
        text = " ".join(self.text.split())
        if speaker_labels == "visible" and self.speaker:
            return f"{self.speaker}: {text}"
        return text


@dataclass
class ProcessingOptions(ModelMixin):
    output_dir: Path = Path("asub-output")
    asr_model: str = "Qwen/Qwen3-ASR-1.7B"
    translation_model: str = "tencent/Hunyuan-MT-Chimera-7B"
    alignment_model: str = "Qwen/Qwen3-ForcedAligner-0.6B"
    source_language: str = "auto"
    target_languages: list[str] = field(default_factory=list)
    formats: list[str] = field(default_factory=lambda: ["srt", "vtt"])
    align: bool = False
    mux: bool = True
    burn: bool = False
    in_place: bool = False
    cleanup: bool = False
    overwrite: bool = False
    resume: bool = True
    skip_existing: bool = True
    chunk_mode: Literal["auto", "always", "never"] = "auto"
    device: str = "auto"
    dtype: Literal["bf16", "fp16", "fp32"] = "bf16"
    quantization: str = "none"
    speaker_labels: Literal["visible", "hidden"] = "visible"
    encoder: str = "hevc_nvenc"
    preset: str = "p5"
    cq: int = 22
    audio_sample_rate: int = 24000
    asr_max_new_tokens: int = 4096
    asr_max_batch_size: int = 128
    asr_max_model_len: int = 16384
    asr_gpu_memory_utilization: float = 0.65
    jobs: int = 2
    max_subtitle_chars: int = 42
    ass_font: str = "Segoe UI"
    ass_font_size: int = 42
    ass_outline: int = 2
    ass_shadow: int = 1
    ass_margin_v: int = 48


@dataclass
class JobMetadata(ModelMixin):
    input_path: Path
    output_dir: Path
    work_dir: Path
    subtitle_dir: Path
    video_dir: Path
    log_path: Path
    metadata_path: Path
    status: dict[str, str] = field(default_factory=dict)
    ffprobe: dict[str, Any] = field(default_factory=dict)
    extracted_audio: Path | None = None
    detected_language: str | None = None
    source_language: str | None = None
    target_languages: list[str] = field(default_factory=list)
    segments: list[CaptionSegment] = field(default_factory=list)
    translations: dict[str, list[CaptionSegment]] = field(default_factory=dict)
    generated_files: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    models: dict[str, str] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)

    def save(self) -> None:
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "JobMetadata":
        data = json.loads(path.read_text(encoding="utf-8"))
        job = cls(
            input_path=Path(data["input_path"]),
            output_dir=Path(data["output_dir"]),
            work_dir=Path(data["work_dir"]),
            subtitle_dir=Path(data["subtitle_dir"]),
            video_dir=Path(data["video_dir"]),
            log_path=Path(data["log_path"]),
            metadata_path=Path(data["metadata_path"]),
        )
        job.status = data.get("status", {})
        job.ffprobe = data.get("ffprobe", {})
        job.extracted_audio = Path(data["extracted_audio"]) if data.get("extracted_audio") else None
        job.detected_language = data.get("detected_language")
        job.source_language = data.get("source_language")
        job.target_languages = list(data.get("target_languages", []))
        job.segments = [CaptionSegment.model_validate(s) for s in data.get("segments", [])]
        job.translations = {
            lang: [CaptionSegment.model_validate(s) for s in segs]
            for lang, segs in data.get("translations", {}).items()
        }
        job.generated_files = data.get("generated_files", {})
        job.warnings = data.get("warnings", [])
        job.errors = data.get("errors", [])
        job.models = data.get("models", {})
        job.options = data.get("options", {})
        return job
