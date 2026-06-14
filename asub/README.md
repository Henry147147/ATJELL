# asub

`asub` is a Linux-first local captioning tool for video files. It extracts audio with ffmpeg, transcribes locally with `Qwen/Qwen3-ASR-1.7B` through the Qwen vLLM backend, uses `Qwen/Qwen3-ForcedAligner-0.6B` for timestamps/alignment, translates captions with `tencent/Hunyuan-MT-Chimera-7B`, and remuxes selectable subtitle tracks by default.

The app is CLI-first and includes a basic optional GUI.

## Quick Start

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest
```

Or create all Linux virtual environments with:

```bash
bash scripts/setup_linux_venvs.sh
source .asub-env
```

Add `--with-gui` if you want the optional PySide6 GUI dependency installed into the core environment. Add `--flash-attn` if your GPU/toolchain supports FlashAttention and you want faster timestamp work.

For real model inference, create separate worker environments as described in [docs/LINUX_SETUP.md](docs/LINUX_SETUP.md). The test suite uses mocked workers and does not download models.

When using the included setup script, `asub` auto-detects `.venv-qwen-asr`, `.venv-mt`, and `.venv-align`; worker environment variables are only needed for custom locations.

## Examples

```bash
asub transcribe "/media/videos/episode 1.mkv" --output captions
asub process "/media/videos/*.mkv" --targets en,es,fr,de,ja --align --output captions
asub process "/media/videos" --targets es,fr --jobs 2 --output captions
asub process "/media/videos/episode 1.mkv" --no-mux
asub process "/media/videos/episode 1.mkv" --targets es --burn --formats srt,vtt,ass --encoder hevc_nvenc --cq 22
asub gui
```

Default `process` behavior writes subtitles and remuxes them into a selectable-subtitle MKV. Burn-in output is opt-in with `--burn`.

See [docs/LINUX_SETUP.md](docs/LINUX_SETUP.md) for installation, worker setup, local fixture creation, model authentication, and troubleshooting.

On Windows, use WSL2 for the CUDA model workers:

```powershell
.\scripts\setup_windows_wsl.ps1
.\scripts\asub_wsl.ps1 doctor
```

See [docs/WINDOWS_WSL_SETUP.md](docs/WINDOWS_WSL_SETUP.md).


• cd /mnt/z/asub

  # Setup Linux environments
  scripts/setup_linux_venvs.sh --flash-attn

  # Activate core CLI env
  . .venv/bin/activate

  # Verify setup
  asub doctor
  python -m pytest

  Run the 5-minute test fixture:

  asub process tests/fixtures/caso_cerrado_5min.mp4 \
    --targets en \
    --output asub-output \
    --jobs 1 \
    --align

  Muxed video output is an MP4 by default. Video and audio streams are copied
  when the MP4 container supports them; SRT subtitles are converted to MP4
  `mov_text` subtitle tracks.

  Run your videos from /mnt/z/C:

  asub process "/mnt/z/C" \
    --targets en \
    --output asub-output \
    --jobs 2 \
    --align

  Useful variants:
  asub process tests/fixtures/caso_cerrado_5min.mp4 --targets en --no-mux
  asub process "/path/to/video.mkv" --targets en --in-place --cleanup

  # Burn-in subtitles, opt-in
    --formats srt,vtt,ass
