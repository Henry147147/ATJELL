# Linux Setup

`asub` targets Linux with local CUDA inference and ffmpeg media handling. Tests use mocked workers by default; real inference requires separate worker environments.

## Core Environment

Install ffmpeg, ffprobe, Python 3.12, and a current NVIDIA driver. On Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg python3.12 python3.12-venv
```

Create all local environments:

```bash
bash scripts/setup_linux_venvs.sh
```

The setup script stores virtual environments under `~/.cache/asub/venvs/<project>-<hash>` by default and writes `.asub-env` in the project root. This avoids broken executable bits and symlinks when the project lives on a mounted share such as `/mnt/z`.

Optional flags:

```bash
bash scripts/setup_linux_venvs.sh --with-gui
bash scripts/setup_linux_venvs.sh --flash-attn
bash scripts/setup_linux_venvs.sh --force
```

Manual core setup:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
python -m pytest
```

## Worker Environments

The main app talks to workers through JSON over stdin/stdout. This keeps model dependency stacks isolated.

Qwen ASR worker with the vLLM backend:

```bash
python3.12 -m venv .venv-qwen-asr
.venv-qwen-asr/bin/python -m pip install --upgrade pip
.venv-qwen-asr/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cu129
.venv-qwen-asr/bin/python -m pip install 'qwen-asr[vllm]'
.venv-qwen-asr/bin/python -m pip install -e .
```

Translation worker:

```bash
python3.12 -m venv .venv-mt
.venv-mt/bin/python -m pip install --upgrade pip
.venv-mt/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cu129
.venv-mt/bin/python -m pip install 'transformers==4.56.0' accelerate
.venv-mt/bin/python -m pip install -e .
```

Alignment worker:

```bash
python3.12 -m venv .venv-align
.venv-align/bin/python -m pip install --upgrade pip
.venv-align/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cu129
.venv-align/bin/python -m pip install qwen-asr
.venv-align/bin/python -m pip install -e .
```

Load the generated environment before running `asub`:

```bash
source .asub-env
```

## Models

The default ASR model is `Qwen/Qwen3-ASR-1.7B`. The ASR worker uses `Qwen3ASRModel.LLM(...)` from `qwen-asr[vllm]` with `gpu_memory_utilization=0.7`, `max_inference_batch_size=128`, and `max_new_tokens=4096`.

Timestamps use `Qwen/Qwen3-ForcedAligner-0.6B`. Installing FlashAttention can improve long-input and timestamp performance:

```bash
bash scripts/setup_linux_venvs.sh --flash-attn
```

`--flash-attn` is best-effort. It installs only when the active `nvcc` CUDA version matches each worker's `torch.version.cuda`; for example, a CUDA 13.2 toolkit cannot build FlashAttention against a Torch CUDA 12.8 wheel.

Optional pre-download:

```bash
source .asub-env
"$ASUB_QWEN_ASR_PYTHON" -m pip install 'huggingface_hub[cli]'
"$(dirname "$ASUB_QWEN_ASR_PYTHON")/huggingface-cli" download Qwen/Qwen3-ASR-1.7B
"$(dirname "$ASUB_QWEN_ASR_PYTHON")/huggingface-cli" download Qwen/Qwen3-ForcedAligner-0.6B
"$ASUB_MT_PYTHON" -m pip install 'huggingface_hub[cli]'
"$(dirname "$ASUB_MT_PYTHON")/huggingface-cli" download tencent/Hunyuan-MT-Chimera-7B
```

## Commands

Transcribe and remux subtitles by default:

```bash
asub process "/path/to/video.mkv" --output asub-output
```

Process a folder with two concurrent video jobs:

```bash
asub process "/path/to/videos" --targets en,es,fr --jobs 2
```

Disable remuxing:

```bash
asub process "/path/to/video.mkv" --no-mux
```

Optional burn-in output:

```bash
asub process "/path/to/video.mkv" --targets es --burn --formats srt,vtt,ass --encoder hevc_nvenc --preset p5 --cq 22
```

## Local Fixture

Create the local 5-minute integration fixture from `/mnt/z/C`:

```bash
mkdir -p tests/fixtures
ffmpeg -hide_banner -y -ss 0 -t 300 \
  -i "/mnt/z/C/Caso Cerrado - Caso Cerrado 5 mil tacos y 2 mil tostadas para el banquete.mp4" \
  -map 0:v:0 -map 0:a:0 -c copy -avoid_negative_ts make_zero \
  tests/fixtures/caso_cerrado_5min.mp4
```

The fixture is intentionally ignored by git.

## Verification

```bash
source .asub-env
python -m pytest
asub doctor
ASUB_RUN_MODEL_TESTS=1 python -m pytest tests/test_real_pipeline.py
```

Troubleshooting:

- Missing ffmpeg or ffprobe: install ffmpeg and ensure both executables are on PATH.
- CUDA unavailable: verify driver, CUDA PyTorch wheel, and `torch.cuda.is_available()`.
- Dependency conflicts: keep the separate worker environments.
- Model download failure: verify network access, cache location, and available disk space.
- GPU out of memory: lower `--asr-max-batch-size`, lower `--asr-gpu-memory-utilization`, use `--chunk-mode always`, or close other GPU processes.
- Failed mux or burn: inspect the logged ffmpeg command and validate subtitle files.
