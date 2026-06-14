from types import SimpleNamespace
import sys
import os

from asub.workers import qwen_asr_worker
from asub.workers.qwen_asr_worker import normalize_qwen_result, transcribe


def test_normalize_qwen_result_with_timestamps():
    result = SimpleNamespace(
        language="Spanish",
        text="hola mundo",
        time_stamps=[
            SimpleNamespace(text="hola", start_time=0.0, end_time=0.5),
            SimpleNamespace(text="mundo", start_time=0.6, end_time=1.0),
        ],
    )
    segments, language, warnings = normalize_qwen_result(result, duration=1.0)
    assert language == "Spanish"
    assert warnings == []
    assert len(segments) == 2
    assert segments[0]["text"] == "hola"
    assert segments[0]["words"][0]["start"] == 0.0


def test_normalize_qwen_result_without_timestamps_uses_coarse_segment():
    result = {"language": "English", "text": "hello world", "time_stamps": None}
    segments, language, warnings = normalize_qwen_result(result, duration=3.0)
    assert language == "English"
    assert len(segments) == 1
    assert segments[0]["start"] == 0.0
    assert segments[0]["end"] == 3.0
    assert "no timestamps" in warnings[0]


def test_transcribe_uses_qwen_vllm_backend(monkeypatch):
    calls = {}
    qwen_asr_worker._MODEL_CACHE.clear()

    class FakeCuda:
        @staticmethod
        def is_available():
            return False

        @staticmethod
        def empty_cache():
            calls["empty_cache"] = True

    fake_torch = SimpleNamespace(bfloat16="bf16", float16="fp16", float32="fp32", cuda=FakeCuda())

    class FakeModel:
        def transcribe(self, **kwargs):
            calls["transcribe"] = kwargs
            return [SimpleNamespace(language="English", text="hello", time_stamps=None)]

    class FakeQwen3ASRModel:
        @staticmethod
        def LLM(**kwargs):
            calls["llm"] = kwargs
            return FakeModel()

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "qwen_asr", SimpleNamespace(Qwen3ASRModel=FakeQwen3ASRModel))
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)

    result = transcribe(
        {
            "audio": "sample.wav",
            "source_language": "en",
            "device": "cuda:0",
            "dtype": "bf16",
            "model": "Qwen/Qwen3-ASR-1.7B",
            "alignment_model": "Qwen/Qwen3-ForcedAligner-0.6B",
            "return_time_stamps": True,
            "duration": 2.0,
            "asr_max_new_tokens": 4096,
            "asr_max_batch_size": 128,
            "asr_max_model_len": 16384,
            "asr_gpu_memory_utilization": 0.65,
        }
    )

    assert result["ok"] is True
    assert calls["llm"]["model"] == "Qwen/Qwen3-ASR-1.7B"
    assert calls["llm"]["gpu_memory_utilization"] == 0.65
    assert calls["llm"]["max_inference_batch_size"] == 128
    assert calls["llm"]["max_model_len"] == 16384
    assert calls["llm"]["forced_aligner"] == "Qwen/Qwen3-ForcedAligner-0.6B"
    assert calls["llm"]["forced_aligner_kwargs"]["dtype"] == "bf16"
    assert calls["transcribe"]["audio"] == "sample.wav"
    assert calls["transcribe"]["language"] == "English"
    assert calls["transcribe"]["return_time_stamps"] is True


def test_transcribe_configures_auto_cuda_before_model_load(monkeypatch):
    calls = {}
    qwen_asr_worker._MODEL_CACHE.clear()

    class FakeCuda:
        @staticmethod
        def is_available():
            return False

    fake_torch = SimpleNamespace(bfloat16="bf16", float16="fp16", float32="fp32", cuda=FakeCuda())

    class FakeModel:
        def transcribe(self, **kwargs):
            return [SimpleNamespace(language="English", text="hello", time_stamps=None)]

    class FakeQwen3ASRModel:
        @staticmethod
        def LLM(**kwargs):
            calls["cuda_visible_devices"] = os.environ.get("CUDA_VISIBLE_DEVICES")
            calls["forced_aligner_device"] = kwargs["forced_aligner_kwargs"]["device_map"]
            calls["gpu_memory_utilization"] = kwargs["gpu_memory_utilization"]
            calls["max_model_len"] = kwargs["max_model_len"]
            return FakeModel()

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "qwen_asr", SimpleNamespace(Qwen3ASRModel=FakeQwen3ASRModel))
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.setattr("asub.workers.cuda.resolve_cuda_visible_devices", lambda device: "1")

    transcribe(
        {
            "audio": "sample.wav",
            "source_language": "en",
            "device": "auto",
            "return_time_stamps": True,
        }
    )

    assert calls["cuda_visible_devices"] == "1"
    assert calls["forced_aligner_device"] == "cuda:0"
    assert calls["gpu_memory_utilization"] == 0.65
    assert calls["max_model_len"] == 16384
