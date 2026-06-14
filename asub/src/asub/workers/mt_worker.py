from __future__ import annotations

import json
import sys
import time
from typing import Any

from asub.languages import hunyuan_name, normalize_language
from asub.workers.cuda import configure_cuda_environment


def _log(message: str) -> None:
    print(f"[mt-worker {time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def _torch_dtype(torch: Any, dtype: str):
    return {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}.get(dtype, torch.bfloat16)


def _prompt(source_code: str, target_code: str, text: str) -> str:
    target = hunyuan_name(target_code)
    source = hunyuan_name(source_code)
    if source_code.startswith("zh") or target_code.startswith("zh"):
        return f"把下面的文本翻译成{target}，不要额外解释。\n\n{text}"
    return f"Translate the following segment into {target}, without additional explanation.\n\n{text}"


def translate(payload: dict[str, Any]) -> dict[str, Any]:
    configure_cuda_environment(payload.get("device", "auto"))
    _log("importing torch/transformers")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_id = payload.get("model") or "tencent/Hunyuan-MT-Chimera-7B"
    source = normalize_language(payload["source_language"])
    target = normalize_language(payload["target_language"])
    dtype = _torch_dtype(torch, payload.get("dtype", "bf16"))
    local_files_only = bool(payload.get("local_files_only", False))
    _log(f"loading tokenizer {model_id}")
    tokenizer = AutoTokenizer.from_pretrained(model_id, local_files_only=local_files_only)
    _log(f"loading model {model_id} dtype={payload.get('dtype', 'bf16')} local_files_only={local_files_only}")
    model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto", torch_dtype=dtype, local_files_only=local_files_only)
    model.eval()
    translated = []
    for idx, raw in enumerate(payload.get("segments", []), start=1):
        _log(f"translating segment {idx}")
        messages = [{"role": "user", "content": _prompt(source, target, raw.get("text", ""))}]
        input_ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False, return_tensors="pt").to(model.device)
        with torch.no_grad():
            outputs = model.generate(
                input_ids,
                max_new_tokens=2048,
                top_k=20,
                top_p=0.6,
                repetition_penalty=1.05,
                temperature=0.7,
            )
        generated = outputs[0][input_ids.shape[-1] :]
        text = tokenizer.decode(generated, skip_special_tokens=True).strip()
        item = dict(raw)
        item["text"] = text
        translated.append(item)
    torch.cuda.empty_cache() if torch.cuda.is_available() else None
    _log("completed")
    return {"ok": True, "segments": translated}


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        print(json.dumps(translate(payload), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
