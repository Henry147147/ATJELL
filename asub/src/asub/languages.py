from __future__ import annotations

from .exceptions import UnsupportedLanguageError

HUNYUAN_LANGUAGES: dict[str, str] = {
    "zh": "Chinese",
    "en": "English",
    "fr": "French",
    "pt": "Portuguese",
    "es": "Spanish",
    "ja": "Japanese",
    "tr": "Turkish",
    "ru": "Russian",
    "ar": "Arabic",
    "ko": "Korean",
    "th": "Thai",
    "it": "Italian",
    "de": "German",
    "vi": "Vietnamese",
    "ms": "Malay",
    "id": "Indonesian",
    "tl": "Filipino",
    "hi": "Hindi",
    "zh-Hant": "Traditional Chinese",
    "pl": "Polish",
    "cs": "Czech",
    "nl": "Dutch",
    "km": "Khmer",
    "my": "Burmese",
    "fa": "Persian",
    "gu": "Gujarati",
    "ur": "Urdu",
    "te": "Telugu",
    "mr": "Marathi",
    "he": "Hebrew",
    "bn": "Bengali",
    "ta": "Tamil",
    "uk": "Ukrainian",
    "bo": "Tibetan",
    "kk": "Kazakh",
    "mn": "Mongolian",
    "ug": "Uyghur",
    "yue": "Cantonese",
}

ALIASES: dict[str, str] = {
    **{code.lower(): code for code in HUNYUAN_LANGUAGES},
    **{name.lower(): code for code, name in HUNYUAN_LANGUAGES.items()},
    "zh-hans": "zh",
    "chinese simplified": "zh",
    "simplified chinese": "zh",
    "traditional chinese": "zh-Hant",
    "filipino": "tl",
    "tagalog": "tl",
    "cantonese": "yue",
    "mandarin": "zh",
    "eng": "en",
    "spa": "es",
    "esp": "es",
    "fre": "fr",
    "fra": "fr",
    "ger": "de",
    "deu": "de",
    "jpn": "ja",
    "kor": "ko",
    "chi": "zh",
    "zho": "zh",
    "por": "pt",
    "ita": "it",
}

ALIGNER_LANGUAGES = {
    "zh": "Chinese",
    "en": "English",
    "yue": "Cantonese",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
    "ru": "Russian",
    "es": "Spanish",
}

QWEN_ASR_LANGUAGES = {
    "zh": "Chinese",
    "en": "English",
    "yue": "Cantonese",
    "ar": "Arabic",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
    "id": "Indonesian",
    "it": "Italian",
    "ko": "Korean",
    "ru": "Russian",
    "th": "Thai",
    "vi": "Vietnamese",
    "ja": "Japanese",
    "tr": "Turkish",
    "hi": "Hindi",
    "ms": "Malay",
    "nl": "Dutch",
    "sv": "Swedish",
    "da": "Danish",
    "fi": "Finnish",
    "pl": "Polish",
    "cs": "Czech",
    "tl": "Filipino",
    "fa": "Persian",
    "el": "Greek",
    "hu": "Hungarian",
    "mk": "Macedonian",
    "ro": "Romanian",
}


def normalize_language(value: str, *, allow_auto: bool = False) -> str:
    raw = value.strip()
    if allow_auto and raw.lower() in {"", "auto", "detect"}:
        return "auto"
    key = raw.replace("_", "-").lower()
    if key in ALIASES:
        return ALIASES[key]
    raise UnsupportedLanguageError(f"Unsupported language: {value!r}")


def parse_targets(value: str | list[str]) -> list[str]:
    parts = value if isinstance(value, list) else value.split(",")
    normalized: list[str] = []
    for part in parts:
        if not str(part).strip():
            continue
        code = normalize_language(str(part))
        if code not in normalized:
            normalized.append(code)
    return normalized


def hunyuan_name(code: str) -> str:
    norm = normalize_language(code)
    return HUNYUAN_LANGUAGES[norm]


def aligner_name(code_or_name: str) -> str | None:
    try:
        code = normalize_language(code_or_name)
    except UnsupportedLanguageError:
        return None
    return ALIGNER_LANGUAGES.get(code)


def qwen_asr_name(code_or_name: str | None) -> str | None:
    if code_or_name is None:
        return None
    try:
        code = normalize_language(code_or_name, allow_auto=True)
    except UnsupportedLanguageError:
        return None
    if code == "auto":
        return None
    return QWEN_ASR_LANGUAGES.get(code)


def source_language_from_probe(probe: dict) -> str | None:
    for stream in probe.get("streams", []):
        if stream.get("codec_type") != "audio":
            continue
        tags = stream.get("tags", {}) or {}
        raw = tags.get("language") or tags.get("LANGUAGE")
        if not raw:
            continue
        try:
            return normalize_language(str(raw))
        except UnsupportedLanguageError:
            return None
    return None
