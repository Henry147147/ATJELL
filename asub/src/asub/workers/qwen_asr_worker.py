from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

from asub.languages import normalize_language, qwen_asr_name
from asub.workers.cuda import configure_cuda_environment, worker_device_map

_MODEL_CACHE: dict[tuple[Any, ...], Any] = {}


def _log(message: str) -> None:
    print(f"[qwen-asr-worker {time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def _torch_dtype(torch: Any, dtype: str):
    return {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}.get(dtype, torch.bfloat16)


def _cuda_visible_device(device: str) -> str | None:
    if not device.startswith("cuda"):
        return None
    if ":" not in device:
        return "0"
    _, index = device.split(":", 1)
    return index or "0"


def _cache_key(kwargs: dict[str, Any]) -> tuple[Any, ...]:
    aligner_kwargs = kwargs.get("forced_aligner_kwargs") or {}
    return (
        kwargs.get("model"),
        kwargs.get("gpu_memory_utilization"),
        kwargs.get("max_inference_batch_size"),
        kwargs.get("max_new_tokens"),
        kwargs.get("local_files_only"),
        kwargs.get("forced_aligner"),
        tuple(sorted(aligner_kwargs.items())),
    )


def _get_attr(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _timestamp_text(item: Any) -> str:
    text = _get_attr(item, "text")
    if text is None:
        text = _get_attr(item, "word")
    if text is None:
        text = _get_attr(item, "token")
    return str(text or "").strip()


def _timestamp_start(item: Any) -> float | None:
    for name in ["start_time", "start", "begin", "begin_time"]:
        found = _float_or_none(_get_attr(item, name))
        if found is not None:
            return found
    return None


def _timestamp_end(item: Any) -> float | None:
    for name in ["end_time", "end", "stop", "end_time"]:
        found = _float_or_none(_get_attr(item, name))
        if found is not None:
            return found
    return None


def _coarse_segment(text: str, duration: float | None) -> dict[str, Any]:
    end = max(0.1, float(duration or 0.1))
    return {
        "index": 1,
        "start": 0.0,
        "end": end,
        "text": text.strip(),
        "speaker": None,
        "words": [],
        "asr_start": 0.0,
        "asr_end": end,
    }


def normalize_qwen_result(result: Any, *, duration: float | None = None) -> tuple[list[dict[str, Any]], str | None, list[str]]:
    language = _get_attr(result, "language")
    text = str(_get_attr(result, "text", "") or "").strip()
    timestamps = _get_attr(result, "time_stamps", None)
    if timestamps is None:
        timestamps = _get_attr(result, "timestamps", None)
    warnings: list[str] = []

    if not timestamps:
        warnings.append("Qwen ASR returned no timestamps; using one coarse segment for the whole audio.")
        return [_coarse_segment(text, duration)], language, warnings

    segments: list[dict[str, Any]] = []
    words: list[dict[str, Any]] = []
    for item in timestamps:
        start = _timestamp_start(item)
        end = _timestamp_end(item)
        item_text = _timestamp_text(item)
        if start is None or end is None or end <= start:
            continue
        words.append({"text": item_text, "start": start, "end": end})
        segments.append(
            {
                "index": len(segments) + 1,
                "start": start,
                "end": end,
                "text": item_text,
                "speaker": None,
                "words": [{"text": item_text, "start": start, "end": end}] if item_text else [],
                "asr_start": start,
                "asr_end": end,
                "aligned_start": start,
                "aligned_end": end,
            }
        )

    if not segments:
        warnings.append("Qwen ASR timestamps could not be parsed; using one coarse segment for the whole audio.")
        return [_coarse_segment(text, duration)], language, warnings
    return segments, language, warnings


def transcribe(payload: dict[str, Any]) -> dict[str, Any]:
    configure_cuda_environment(payload.get("device", "auto"))
    _log("importing torch/qwen_asr")
    import torch
    from qwen_asr import Qwen3ASRModel

    model_id = payload.get("model") or "Qwen/Qwen3-ASR-1.7B"
    dtype = _torch_dtype(torch, payload.get("dtype", "bf16"))
    source_language = payload.get("source_language")
    qwen_language = qwen_asr_name(source_language)
    return_timestamps = bool(payload.get("return_time_stamps", True))
    local_files_only = bool(payload.get("local_files_only", False))
    device_map = worker_device_map(payload.get("device", "auto"))

    kwargs: dict[str, Any] = {
        "model": model_id,
        "gpu_memory_utilization": float(payload.get("asr_gpu_memory_utilization", 0.65)),
        "max_inference_batch_size": int(payload.get("asr_max_batch_size", 128)),
        "max_model_len": int(payload.get("asr_max_model_len", 16384)),
        "max_new_tokens": int(payload.get("asr_max_new_tokens", 4096)),
    }
    if local_files_only:
        kwargs["local_files_only"] = True
    if return_timestamps:
        kwargs["forced_aligner"] = payload.get("alignment_model", "Qwen/Qwen3-ForcedAligner-0.6B")
        kwargs["forced_aligner_kwargs"] = {
            "dtype": dtype,
            "device_map": device_map,
        }
        if local_files_only:
            kwargs["forced_aligner_kwargs"]["local_files_only"] = True

    key = _cache_key(kwargs)
    model = _MODEL_CACHE.get(key)
    if model is None:
        _log(f"loading vLLM model {model_id} local_files_only={local_files_only}")
        model = Qwen3ASRModel.LLM(**kwargs)
        _MODEL_CACHE[key] = model
    else:
        _log(f"reusing vLLM model {model_id}")
    _log(f"transcribing language={qwen_language or 'auto'} timestamps={return_timestamps}")
    results = model.transcribe(
        audio=payload["audio"],
        language=qwen_language,
        return_time_stamps=return_timestamps,
    )
    if isinstance(payload["audio"], list) and isinstance(results, list):
        durations = payload.get("durations") or [payload.get("duration")] * len(results)
        normalized_results = []
        for result, duration in zip(results, durations):
            segments, detected_language, warnings = normalize_qwen_result(result, duration=duration)
            normalized_results.append(
                {
                    "segments": segments,
                    "detected_language": detected_language,
                    "warnings": warnings,
                }
            )
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        _log("completed")
        return {"ok": True, "results": normalized_results}

    result = results[0] if isinstance(results, list) else results
    segments, detected_language, warnings = normalize_qwen_result(result, duration=payload.get("duration"))
    torch.cuda.empty_cache() if torch.cuda.is_available() else None
    _log("completed")
    return {"ok": True, "segments": segments, "detected_language": detected_language, "warnings": warnings}


def main() -> None:
    failed = False
    saw_payload = False
    for raw in sys.stdin:
        if not raw.strip():
            continue
        saw_payload = True
        try:
            payload = json.loads(raw)
            print(json.dumps(transcribe(payload), ensure_ascii=False), flush=True)
        except Exception as exc:
            failed = True
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), flush=True)
    if not saw_payload:
        try:
            payload = json.loads(sys.stdin.read() or "{}")
            print(json.dumps(transcribe(payload), ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), flush=True)
            sys.exit(1)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
