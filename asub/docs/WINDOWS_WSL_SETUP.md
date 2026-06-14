# Windows + WSL Setup

Native Windows is not the supported CUDA target for the Qwen ASR worker because it uses the vLLM backend. Run the model environments under WSL2 and launch them from PowerShell.

## Setup

From PowerShell in the repository root:

```powershell
.\scripts\setup_windows_wsl.ps1
```

The setup script calls `scripts/setup_linux_venvs.sh --flash-attn` inside WSL. It stores virtual environments under WSL's home cache and writes `.asub-env` in the repo.

Useful options:

```powershell
.\scripts\setup_windows_wsl.ps1 -Force
.\scripts\setup_windows_wsl.ps1 -WithGui
.\scripts\setup_windows_wsl.ps1 -NoFlashAttn
```

## Run

Use the PowerShell launcher:

```powershell
.\scripts\asub_wsl.ps1 doctor
.\scripts\asub_wsl.ps1 process "/mnt/z/C/path/to/video.mp4" --targets en --align --output asub-output
```

Pass Linux/WSL paths such as `/mnt/z/C/...` to `asub`.

## RTX 5090 And FlashAttention

RTX 5090 uses Blackwell compute capability 12.0. The setup script sets `FLASH_ATTN_CUDA_ARCHS=120` by default and looks for a CUDA toolkit matching `torch.version.cuda`, for example `/usr/local/cuda-12.9` for PyTorch `cu129`.

If FlashAttention is skipped, check:

```bash
source .asub-env
"$ASUB_ALIGN_PYTHON" - <<'PY'
import torch
print(torch.__version__, torch.version.cuda)
PY
nvcc --version
```

Install or select the CUDA toolkit version that matches PyTorch, then rerun setup with `-Force`.
