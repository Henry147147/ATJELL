from pathlib import Path


def test_no_legacy_asr_references_remain():
    root = Path(__file__).resolve().parents[1]
    legacy_terms = [
        "".join(["vibe", "voice"]),
        "".join(["bea", "lore"]) + "/" + "".join(["vibe", "voice"]) + "-asr-" + "fp8",
        "asr-" + "fp8",
    ]
    searched = [
        *root.glob("*.md"),
        *root.glob("*.toml"),
        *root.glob("scripts/*"),
        *root.glob("docs/*"),
        *root.glob("src/**/*.py"),
        *root.glob("tests/**/*.py"),
    ]
    offenders = []
    for path in searched:
        if path == Path(__file__).resolve():
            continue
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").casefold()
        for term in legacy_terms:
            if term in text:
                offenders.append(str(path.relative_to(root)))
                break

    assert offenders == []
