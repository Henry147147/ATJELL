#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

FORCE=0
WITH_GUI=0
INSTALL_FLASH_ATTN=0

usage() {
  cat <<'EOF'
Usage:
  bash scripts/setup_linux_venvs.sh [--force] [--with-gui] [--flash-attn]

Options:
  --force       Recreate existing .venv, .venv-qwen-asr, .venv-mt, and .venv-align.
  --with-gui    Install the optional PySide6 GUI dependency into the core .venv.
  --flash-attn  Install flash-attn in the Qwen ASR and align worker environments.

Environment overrides:
  ASUB_PYTHON       Python command to use. Default: python3.12
  ASUB_TORCH_INDEX  PyTorch index URL. Default: https://download.pytorch.org/whl/cu129
  ASUB_VENV_ROOT    Directory for venvs. Default: ~/.cache/asub/venvs/<project>-<hash>
EOF
}

while (($#)); do
  case "$1" in
    --force) FORCE=1 ;;
    --with-gui) WITH_GUI=1 ;;
    --flash-attn) INSTALL_FLASH_ATTN=1 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "ERROR: Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

ASUB_PYTHON="${ASUB_PYTHON:-python3.12}"
ASUB_TORCH_INDEX="${ASUB_TORCH_INDEX:-https://download.pytorch.org/whl/cu129}"
PROJECT_KEY="$(printf '%s' "$ROOT" | sha1sum | cut -c1-12)"
ASUB_VENV_ROOT="${ASUB_VENV_ROOT:-${XDG_CACHE_HOME:-$HOME/.cache}/asub/venvs/$(basename "$ROOT")-$PROJECT_KEY}"
CORE_VENV="$ASUB_VENV_ROOT/.venv"
QWEN_ASR_VENV="$ASUB_VENV_ROOT/.venv-qwen-asr"
MT_VENV="$ASUB_VENV_ROOT/.venv-mt"
ALIGN_VENV="$ASUB_VENV_ROOT/.venv-align"

echo "asub Linux venv setup"
echo "Root: $ROOT"
echo "Venv root: $ASUB_VENV_ROOT"
echo "Python command: $ASUB_PYTHON"
echo "PyTorch CUDA index: $ASUB_TORCH_INDEX"
echo

"$ASUB_PYTHON" --version

create_venv() {
  local venv="$1"
  if [[ -x "$venv/bin/python" && "$FORCE" -eq 0 ]] && "$venv/bin/python" --version >/dev/null 2>&1; then
    echo "Reusing $venv"
    return
  fi
  if [[ -d "$venv" ]]; then
    rm -rf "$venv"
  fi
  mkdir -p "$(dirname "$venv")"
  "$ASUB_PYTHON" -m venv "$venv"
}

install_common() {
  local venv="$1"
  "$venv/bin/python" -m pip install --upgrade pip
}

cuda_version_from_nvcc() {
  local nvcc_path="$1"
  "$nvcc_path" --version 2>/dev/null | sed -n 's/.*release \([0-9][0-9]*\.[0-9][0-9]*\).*/\1/p' | head -1
}

nvcc_for_cuda_version() {
  local cuda_version="$1"
  local candidate
  for candidate in \
    "/usr/local/cuda-$cuda_version/bin/nvcc" \
    "/usr/local/cuda-${cuda_version%.*}/bin/nvcc" \
    "$(command -v nvcc || true)"
  do
    if [[ -n "$candidate" && -x "$candidate" ]] && [[ "$(cuda_version_from_nvcc "$candidate")" == "$cuda_version" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

torch_cuda_version() {
  local venv="$1"
  "$venv/bin/python" - <<'PY'
import torch
print(torch.version.cuda or "")
PY
}

install_flash_attn_if_compatible() {
  local venv="$1"
  local label="$2"
  local torch_cuda
  torch_cuda="$(torch_cuda_version "$venv")"
  if [[ -z "$torch_cuda" ]]; then
    echo "Skipping flash-attn for $label: torch reports no CUDA version."
    return 0
  fi

  local nvcc_path
  nvcc_path="$(nvcc_for_cuda_version "$torch_cuda" || true)"
  if [[ -z "$nvcc_path" ]]; then
    local active_nvcc
    active_nvcc="$(command -v nvcc || true)"
    if [[ -n "$active_nvcc" ]]; then
      echo "Skipping flash-attn for $label: torch CUDA is $torch_cuda but PATH nvcc is $(cuda_version_from_nvcc "$active_nvcc")."
    else
      echo "Skipping flash-attn for $label: nvcc is not on PATH."
    fi
    echo "Install a CUDA $torch_cuda toolkit, or put its nvcc on PATH, then rerun --flash-attn."
    return 0
  fi

  local cuda_home
  cuda_home="$(cd "$(dirname "$nvcc_path")/.." && pwd -P)"
  echo "Installing flash-attn for $label with CUDA_HOME=$cuda_home"
  CUDA_HOME="$cuda_home" \
    PATH="$cuda_home/bin:$PATH" \
    LD_LIBRARY_PATH="$cuda_home/lib64:${LD_LIBRARY_PATH:-}" \
    FLASH_ATTN_CUDA_ARCHS="${FLASH_ATTN_CUDA_ARCHS:-120}" \
    MAX_JOBS="${MAX_JOBS:-4}" \
    "$venv/bin/python" -m pip install flash-attn --no-build-isolation
}

echo
echo "=== Core CLI/test environment ==="
create_venv "$CORE_VENV"
install_common "$CORE_VENV"
if [[ "$WITH_GUI" -eq 1 ]]; then
  "$CORE_VENV/bin/python" -m pip install -e ".[test,gui]"
else
  "$CORE_VENV/bin/python" -m pip install -e ".[test]"
fi

echo
echo "=== Qwen ASR vLLM worker: $QWEN_ASR_VENV ==="
create_venv "$QWEN_ASR_VENV"
install_common "$QWEN_ASR_VENV"
"$QWEN_ASR_VENV/bin/python" -m pip install torch --index-url "$ASUB_TORCH_INDEX"
"$QWEN_ASR_VENV/bin/python" -m pip install "qwen-asr[vllm]"
if [[ "$INSTALL_FLASH_ATTN" -eq 1 ]]; then
  install_flash_attn_if_compatible "$QWEN_ASR_VENV" "Qwen ASR"
fi
"$QWEN_ASR_VENV/bin/python" -m pip install -e .

echo
echo "=== Translation worker: $MT_VENV ==="
create_venv "$MT_VENV"
install_common "$MT_VENV"
"$MT_VENV/bin/python" -m pip install torch --index-url "$ASUB_TORCH_INDEX"
"$MT_VENV/bin/python" -m pip install "transformers==4.56.0" accelerate
"$MT_VENV/bin/python" -m pip install -e .

echo
echo "=== Alignment worker: $ALIGN_VENV ==="
create_venv "$ALIGN_VENV"
install_common "$ALIGN_VENV"
"$ALIGN_VENV/bin/python" -m pip install torch --index-url "$ASUB_TORCH_INDEX"
"$ALIGN_VENV/bin/python" -m pip install qwen-asr
if [[ "$INSTALL_FLASH_ATTN" -eq 1 ]]; then
  install_flash_attn_if_compatible "$ALIGN_VENV" "alignment"
fi
"$ALIGN_VENV/bin/python" -m pip install -e .

cat > "$ROOT/.asub-env" <<EOF
export HF_HUB_DISABLE_XET=1
export ASUB_QWEN_ASR_PYTHON="$QWEN_ASR_VENV/bin/python"
export ASUB_MT_PYTHON="$MT_VENV/bin/python"
export ASUB_ALIGN_PYTHON="$ALIGN_VENV/bin/python"
export PATH="$CORE_VENV/bin:\$PATH"
EOF

cat <<EOF

Setup complete.

Load this shell environment:
  source .asub-env

Verify:
  python -m pytest
  asub doctor
EOF
