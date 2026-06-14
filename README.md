# Auto Transcription for Jellyfin

Docker-first Jellyfin plugin and ASR service for generating missing sidecar subtitles with Qwen ASR, Qwen forced alignment, and Hy-MT2 translation models.

## Defaults
- Target subtitle languages: `en,es`
- ASR: `Qwen/Qwen3-ASR-1.7B`
- Forced aligner: `Qwen/Qwen3-ForcedAligner-0.6B`
- Translation: `tencent/Hy-MT2-7B-FP8`
- Subtitle format: `srt`
- Output: sidecar files only, named like `Movie.en.srt`
- Jellyfin service URL: `http://asub-api:8765`

## Docker Install
Set `MEDIA_ROOT` to the host path containing your Jellyfin media, then run the GPU stack:

```bash
docker compose up --build
```

The default compose file builds Jellyfin with the plugin installed and reserves one NVIDIA GPU for `asub-api`. The GPU service sets NVIDIA runtime variables and vLLM/PyTorch memory defaults intended for a 5070 Ti class card.

For CPU mode, start Jellyfin with the CPU ASR service explicitly:

```bash
docker compose --profile cpu up --build jellyfin asub-api-cpu
```

The CPU service advertises the `asub-api` network alias, so the plugin default URL still works inside Compose.

Open Jellyfin at `http://localhost:8096`, finish first-run setup, then go to `Dashboard -> Plugins -> Auto Transcription` and confirm:

- `ASR service URL`: `http://asub-api:8765`
- `API token`: same value as `ASUB_API_TOKEN`, or blank when unset
- `Target languages`: `en,es`, or your desired comma-separated language codes
- `Maximum jobs per scan`: how many media items the scheduled task may submit in one run

Run the scheduled task from `Dashboard -> Scheduled Tasks -> Generate Missing Subtitles`, or wait for the daily trigger.

## Manual Jellyfin Plugin Install
Use this when Jellyfin is already installed outside the provided Compose stack.

1. Publish the plugin:

   ```bash
   dotnet publish src/Jellyfin.Plugin.AutoTranscription/Jellyfin.Plugin.AutoTranscription.csproj \
     -c Release \
     -o artifacts/AutoTranscription
   ```

2. Create a plugin directory under Jellyfin's config path and copy the DLL:

   ```bash
   mkdir -p /path/to/jellyfin/config/plugins/AutoTranscription
   cp artifacts/AutoTranscription/Jellyfin.Plugin.AutoTranscription.dll \
     /path/to/jellyfin/config/plugins/AutoTranscription/
   ```

3. Restart Jellyfin.

4. Start the ASR service with access to the same media paths Jellyfin sees:

   ```bash
   MEDIA_ROOT=/path/to/media docker compose up --build asub-api
   ```

   For CPU-only service testing:

   ```bash
   MEDIA_ROOT=/path/to/media docker compose --profile cpu up --build asub-api-cpu
   ```

5. In Jellyfin, open `Dashboard -> Plugins -> Auto Transcription` and set the service URL. For Jellyfin running on the host, use `http://127.0.0.1:8765`. For another container on the same Docker network, use `http://asub-api:8765`.

## Configuration
Key environment variables:

- `ASUB_TARGET_LANGS`: comma-separated target languages, default `en,es`
- `ASUB_ASR_MODEL`: `Qwen/Qwen3-ASR-1.7B` or `Qwen/Qwen3-ASR-0.6B`
- `ASUB_TRANSLATION_SIZE`: `small`, `medium`, or `large`
- `ASUB_TRANSLATION_MODEL`: explicit model override
- `ASUB_DEVICE`: `auto`, `cuda:0`, or `cpu`
- `ASUB_MAX_CONCURRENT_ASR`, `ASUB_MAX_CONCURRENT_ALIGNMENT`, `ASUB_MAX_CONCURRENT_TRANSLATION`
- `ASUB_UNLOAD_ON_IDLE`: default `true`

Translation model tiers:

- `small`: `tencent/Hy-MT2-1.8B-FP8`
- `medium`: `tencent/Hy-MT2-7B-FP8`
- `large`: `tencent/Hy-MT2-30B-A3B-FP8`

The ASR model can be set to `Qwen/Qwen3-ASR-1.7B` or the lower-memory `Qwen/Qwen3-ASR-0.6B`. The forced aligner defaults to `Qwen/Qwen3-ForcedAligner-0.6B`.

## Development

```bash
dotnet test AutoTranscription.slnx
uv run --extra test pytest tests/python -q
uv run --extra test pytest asub/tests tests/python -q
docker compose config
docker compose --profile cpu config
docker compose build jellyfin
```

The `asub-api` image downloads and installs CUDA, vLLM, Qwen ASR, and model-serving dependencies. Build it before release on a GPU host:

```bash
docker compose build asub-api
```
