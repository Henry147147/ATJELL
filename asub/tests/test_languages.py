import pytest

from asub.exceptions import UnsupportedLanguageError
from asub.languages import aligner_name, hunyuan_name, normalize_language, parse_targets, qwen_asr_name, source_language_from_probe


def test_parse_language_codes_and_names():
    assert parse_targets("English, es, Traditional Chinese, tagalog") == ["en", "es", "zh-Hant", "tl"]
    assert hunyuan_name("ja") == "Japanese"
    assert normalize_language("auto", allow_auto=True) == "auto"


def test_unsupported_language_fails_clearly():
    with pytest.raises(UnsupportedLanguageError):
        parse_targets("klingon")


def test_aligner_supported_subset():
    assert aligner_name("English") == "English"
    assert aligner_name("pl") is None


def test_source_language_from_ffprobe_audio_tag():
    probe = {"streams": [{"codec_type": "video"}, {"codec_type": "audio", "tags": {"language": "spa"}}]}
    assert source_language_from_probe(probe) == "es"


def test_qwen_asr_language_names():
    assert qwen_asr_name("auto") is None
    assert qwen_asr_name("es") == "Spanish"
    assert qwen_asr_name("tagalog") == "Filipino"
