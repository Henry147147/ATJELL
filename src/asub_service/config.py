from __future__ import annotations

import os
from dataclasses import dataclass, field

from asub.languages import parse_targets

TRANSLATION_MODELS = {
    "small": "tencent/Hy-MT2-1.8B-FP8",
    "medium": "tencent/Hy-MT2-7B-FP8",
    "large": "tencent/Hy-MT2-30B-A3B-FP8",
}


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return int(value)


@dataclass(frozen=True)
class ServiceConfig:
    target_languages: list[str] = field(default_factory=lambda: ["en", "es"])
    subtitle_formats: list[str] = field(default_factory=lambda: ["srt"])
    asr_model: str = "Qwen/Qwen3-ASR-1.7B"
    alignment_model: str = "Qwen/Qwen3-ForcedAligner-0.6B"
    translation_size: str = "medium"
    translation_model: str = "tencent/Hy-MT2-7B-FP8"
    device: str = "auto"
    dtype: str = "bf16"
    gpu_memory_utilization: float = 0.72
    max_concurrent_asr: int = 1
    max_concurrent_alignment: int = 1
    max_concurrent_translation: int = 2
    unload_on_idle: bool = True
    api_token: str = ""

    @classmethod
    def from_env(cls) -> "ServiceConfig":
        device = os.environ.get("ASUB_DEVICE", "auto").strip() or "auto"
        translation_size = os.environ.get("ASUB_TRANSLATION_SIZE", "medium").strip().lower() or "medium"
        translation_model = os.environ.get("ASUB_TRANSLATION_MODEL")
        if not translation_model:
            translation_model = TRANSLATION_MODELS.get(translation_size, TRANSLATION_MODELS["medium"])

        asr_concurrency = _int_env("ASUB_MAX_CONCURRENT_ASR", 1)
        align_concurrency = _int_env("ASUB_MAX_CONCURRENT_ALIGNMENT", 1)
        translation_concurrency = _int_env("ASUB_MAX_CONCURRENT_TRANSLATION", 2)
        if device == "cpu":
            asr_concurrency = 1
            align_concurrency = 1
            translation_concurrency = 1

        return cls(
            target_languages=parse_targets(os.environ.get("ASUB_TARGET_LANGS", "en,es")),
            subtitle_formats=[part.strip().lower().lstrip(".") for part in os.environ.get("ASUB_SUBTITLE_FORMATS", "srt").split(",") if part.strip()],
            asr_model=os.environ.get("ASUB_ASR_MODEL", "Qwen/Qwen3-ASR-1.7B"),
            alignment_model=os.environ.get("ASUB_ALIGNMENT_MODEL", "Qwen/Qwen3-ForcedAligner-0.6B"),
            translation_size=translation_size,
            translation_model=translation_model,
            device=device,
            dtype=os.environ.get("ASUB_DTYPE", "bf16"),
            gpu_memory_utilization=float(os.environ.get("ASUB_GPU_MEMORY_UTILIZATION", "0.72")),
            max_concurrent_asr=asr_concurrency,
            max_concurrent_alignment=align_concurrency,
            max_concurrent_translation=translation_concurrency,
            unload_on_idle=_bool_env("ASUB_UNLOAD_ON_IDLE", True),
            api_token=os.environ.get("ASUB_API_TOKEN", ""),
        )
