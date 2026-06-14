from __future__ import annotations

import json
import sys
import time
from typing import Any

from asub.workers.cuda import configure_cuda_environment, worker_device_map


def _log(message: str) -> None:
    print(f"[align-worker {time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def _torch_dtype(torch: Any, dtype: str):
    return {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}.get(dtype, torch.bfloat16)


def align(payload: dict[str, Any]) -> dict[str, Any]:
    configure_cuda_environment(payload.get("device", "auto"))
    _log("importing torch/qwen_asr")
    import torch
    from qwen_asr import Qwen3ForcedAligner

    model_id = payload.get("model") or "Qwen/Qwen3-ForcedAligner-0.6B"
    dtype = _torch_dtype(torch, payload.get("dtype", "bf16"))
    kwargs = {"dtype": dtype, "device_map": worker_device_map(payload.get("device", "auto"))}
    if payload.get("local_files_only", False):
        kwargs["local_files_only"] = True
    _log(f"loading model {model_id} local_files_only={bool(payload.get('local_files_only', False))}")
    model = Qwen3ForcedAligner.from_pretrained(model_id, **kwargs)
    output = []
    for idx, raw in enumerate(payload.get("segments", []), start=1):
        _log(f"aligning segment {idx}")
        item = dict(raw)
        item["asr_start"] = raw.get("asr_start", raw.get("start"))
        item["asr_end"] = raw.get("asr_end", raw.get("end"))
        results = model.align(audio=payload["audio"], text=raw.get("text", ""), language=payload["language"])
        words = []
        for token in (results[0] if results else []):
            words.append({"text": token.text, "start": float(token.start_time), "end": float(token.end_time)})
        if words:
            item["words"] = words
            item["aligned_start"] = words[0]["start"]
            item["aligned_end"] = words[-1]["end"]
            item["start"] = item["aligned_start"]
            item["end"] = item["aligned_end"]
        output.append(item)
    torch.cuda.empty_cache() if torch.cuda.is_available() else None
    _log("completed")
    return {"ok": True, "segments": output}


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        print(json.dumps(align(payload), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
