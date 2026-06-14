# Auto Transcription Agent Guide

## Project Goal
Build and maintain a Jellyfin 10.11.x plugin plus Dockerized ASR service that generates missing sidecar subtitles for configured target languages. The default target languages are `en,es`.

## Non-Negotiable Behavior
- Only write external sidecar subtitles next to media files. Do not burn subtitles, remux media, replace media, or delete media.
- Treat existing Jellyfin subtitle streams as satisfying a language when `TreatEmbeddedSubtitlesAsPresent` is true. This is the default.
- Sidecar names must follow Jellyfin conventions: `<media-stem>.<language>.<format>`, for example `Movie.en.srt`.
- Keep Docker-first operation: Jellyfin and `asub-api` must mount the same media path so the plugin can pass media paths directly.
- Unload ASR/alignment/translation resources after the service queue drains when `ASUB_UNLOAD_ON_IDLE=true`.

## Model Defaults
- ASR default: `Qwen/Qwen3-ASR-1.7B`.
- ASR low-VRAM option: `Qwen/Qwen3-ASR-0.6B`.
- Forced aligner: `Qwen/Qwen3-ForcedAligner-0.6B`.
- Translation tiers:
  - `small`: `tencent/Hy-MT2-1.8B-FP8`
  - `medium`: `tencent/Hy-MT2-7B-FP8`
  - `large`: `tencent/Hy-MT2-30B-A3B-FP8`
- Balanced 5070 Ti defaults use `medium`, BF16/FP8-capable models, one ASR job, one alignment job, and two translation jobs.

## Coding Guidelines
- Use tests first for behavior changes. Keep C# scan planning and Python service orchestration independently testable.
- Keep Jellyfin-specific API usage behind adapters; core scan decisions should not require a Jellyfin runtime.
- Keep model/runtime settings configurable through `compose.yaml` environment variables.
- Avoid broad refactors of copied `asub` unless needed for sidecar-only service behavior.
- Commit and push after each major change with a detailed message and verification commands.

## Verification
- C#: `dotnet test AutoTranscription.slnx`
- Python service: `uv run --extra test pytest tests/python -q`
- Docker config: `docker compose config`
- Wider copied-asub regression when changing `asub`: `uv run --extra test pytest asub/tests tests/python -q`
