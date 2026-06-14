from asub_service.config import ServiceConfig


def test_config_defaults_target_english_and_spanish(monkeypatch):
    monkeypatch.delenv("ASUB_TARGET_LANGS", raising=False)

    config = ServiceConfig.from_env()

    assert config.target_languages == ["en", "es"]
    assert config.asr_model == "Qwen/Qwen3-ASR-1.7B"
    assert config.translation_model == "tencent/Hy-MT2-7B-FP8"
    assert config.device == "auto"
    assert config.unload_on_idle is True


def test_config_cpu_mode_disables_gpu_concurrency(monkeypatch):
    monkeypatch.setenv("ASUB_DEVICE", "cpu")
    monkeypatch.setenv("ASUB_MAX_CONCURRENT_ASR", "4")
    monkeypatch.setenv("ASUB_MAX_CONCURRENT_TRANSLATION", "8")

    config = ServiceConfig.from_env()

    assert config.device == "cpu"
    assert config.max_concurrent_asr == 1
    assert config.max_concurrent_translation == 1


def test_config_selects_translation_model_by_size(monkeypatch):
    monkeypatch.setenv("ASUB_TRANSLATION_SIZE", "small")
    assert ServiceConfig.from_env().translation_model == "tencent/Hy-MT2-1.8B-FP8"

    monkeypatch.setenv("ASUB_TRANSLATION_SIZE", "large")
    assert ServiceConfig.from_env().translation_model == "tencent/Hy-MT2-30B-A3B-FP8"

    monkeypatch.setenv("ASUB_TRANSLATION_MODEL", "custom/model")
    assert ServiceConfig.from_env().translation_model == "custom/model"
