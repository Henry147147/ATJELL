# Auto Transcription for Jellyfin

Docker-first Jellyfin plugin and ASR service for generating missing sidecar subtitles with Qwen ASR, Qwen forced alignment, and Hy-MT2 translation models.

## Defaults
- Target subtitle languages: `en,es`
- ASR: `Qwen/Qwen3-ASR-1.7B`
- Forced aligner: `Qwen/Qwen3-ForcedAligner-0.6B`
- Translation: `tencent/Hy-MT2-7B-FP8`
- Subtitle format: `srt`
- Output: sidecar files only, named like `Movie.en.srt`

## Run
Set `MEDIA_ROOT` to the host path containing your Jellyfin media, then run:

```bash
docker compose up --build
```

The default compose file reserves one NVIDIA GPU for `asub-api`. For CPU mode:

```bash
docker compose --profile cpu up --build asub-api-cpu
```

## Configuration
Key environment variables:

- `ASUB_TARGET_LANGS`: comma-separated target languages, default `en,es`
- `ASUB_ASR_MODEL`: `Qwen/Qwen3-ASR-1.7B` or `Qwen/Qwen3-ASR-0.6B`
- `ASUB_TRANSLATION_SIZE`: `small`, `medium`, or `large`
- `ASUB_TRANSLATION_MODEL`: explicit model override
- `ASUB_DEVICE`: `auto`, `cuda:0`, or `cpu`
- `ASUB_MAX_CONCURRENT_ASR`, `ASUB_MAX_CONCURRENT_ALIGNMENT`, `ASUB_MAX_CONCURRENT_TRANSLATION`
- `ASUB_UNLOAD_ON_IDLE`: default `true`

## Development

```bash
uv run --extra test pytest tests/python -q
dotnet test AutoTranscription.slnx
docker compose config
```
