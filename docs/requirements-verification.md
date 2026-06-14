# Requirements Verification

This checklist maps the original project requirements to implementation and verification commands.

## Jellyfin Plugin

- [x] Scheduled task scans media for missing configured subtitle languages.
  - Implementation: `GenerateSubtitlesTask`, `JellyfinLibrarySubtitleScanner`, `SubtitleScanTaskRunner`.
  - Verification: `dotnet test AutoTranscription.slnx`.
- [x] User-configurable target languages, defaulting to `en,es`.
  - Implementation: `PluginConfiguration.TargetLanguages`, Jellyfin config page, `ASUB_TARGET_LANGS`.
  - Verification: `LanguageConfigurationTests`, `PluginPageTests`, Python config tests.
- [x] Existing embedded or sidecar subtitle streams can satisfy a target language.
  - Implementation: `SubtitleScanPlanner`.
  - Verification: `SubtitleScanPlannerTests`.
- [x] Generated subtitles are sidecar files only.
  - Implementation: Python runner forces `mux=False`, `burn=False`, `in_place=False`.
  - Verification: `tests/python/test_runner.py`.
- [x] Jellyfin import is triggered after completed service jobs.
  - Implementation: `JellyfinSubtitleItemRefresher`.
  - Verification: `SubtitleScanTaskRunnerTests`.
- [x] Per-scan submission cap is enforced.
  - Implementation: `PluginConfiguration.MaxSubmittedJobs`.
  - Verification: `RunnerHonorsMaxSubmittedJobsPerRun`.
- [x] Configured scan batch jobs are submitted concurrently.
  - Implementation: `SubtitleScanTaskRunner`.
  - Verification: `RunnerSubmitsConfiguredBatchConcurrently`.

## ASR Service

- [x] Copied `asub` codebase is included in this project.
  - Implementation: `asub/`.
  - Verification: `uv run --extra test pytest asub/tests tests/python -q`.
- [x] HTTP service accepts media paths and writes sidecars next to media.
  - Implementation: `asub_service.api`, `asub_service.runner`, `asub_service.sidecars`.
  - Verification: `tests/python/test_api.py`, `tests/python/test_sidecars.py`, `tests/python/test_runner.py`.
- [x] API token protection is available for job endpoints while health remains unauthenticated.
  - Implementation: `ASUB_API_TOKEN`.
  - Verification: `tests/python/test_api.py`.
- [x] Model resources unload after the queue drains when enabled.
  - Implementation: `SubtitleJobQueue` calls the runner unload hook after drain.
  - Verification: `tests/python/test_jobs.py`.
- [x] CPU inference mode clamps concurrency to one job per stage.
  - Implementation: `ServiceConfig.from_env`.
  - Verification: `tests/python/test_config.py`.
- [x] Concurrent service requests are bounded by stage concurrency and unload only after all running jobs finish.
  - Implementation: `SubtitleJobQueue`.
  - Verification: `test_queue_runs_concurrent_drains_up_to_configured_stage_limit`.

## Models And Acceleration

- [x] Qwen ASR small and larger model options are configurable.
  - Defaults: `Qwen/Qwen3-ASR-1.7B`, CPU/low-VRAM option `Qwen/Qwen3-ASR-0.6B`.
- [x] Qwen forced aligner is configurable.
  - Default: `Qwen/Qwen3-ForcedAligner-0.6B`.
- [x] Translation model size tiers are configurable.
  - `small`: `tencent/Hy-MT2-1.8B-FP8`
  - `medium`: `tencent/Hy-MT2-7B-FP8`
  - `large`: `tencent/Hy-MT2-30B-A3B-FP8`
- [x] 5070 Ti defaults favor GPU acceleration and bounded VRAM use.
  - Implementation: `compose.yaml` sets NVIDIA device reservation, BF16/FP8-oriented models, vLLM and PyTorch memory environment variables.
- [x] Stage concurrency is configurable for ASR, forced alignment, and translation.
  - Implementation: `ASUB_MAX_CONCURRENT_ASR`, `ASUB_MAX_CONCURRENT_ALIGNMENT`, `ASUB_MAX_CONCURRENT_TRANSLATION`.
  - The service uses the largest configured stage value as its request concurrency cap so vLLM-backed workers can handle parallel requests when VRAM permits.

## Docker And Installation

- [x] Simple Compose deployment is provided.
  - Implementation: `compose.yaml`.
  - Verification: `docker compose config`, `docker compose --profile cpu config`.
- [x] GPU service passes one NVIDIA GPU into the container.
  - Implementation: Compose device reservation and NVIDIA environment variables.
- [x] CPU service can be started with the same Jellyfin plugin URL.
  - Implementation: `asub-api-cpu` profile service with `asub-api` network alias.
- [x] Jellyfin plugin installation instructions are documented.
  - Implementation: README Docker and manual install sections.

## Release Verification Commands

Run these before release:

```bash
dotnet test AutoTranscription.slnx
uv run --extra test pytest asub/tests tests/python -q
docker compose config
docker compose --profile cpu config
docker compose build jellyfin
docker compose build asub-api
```

If `docker compose build asub-api` is not run locally because the CUDA/vLLM image is too large for the current machine, document that exception in the release notes and run it on a GPU build host before tagging.
