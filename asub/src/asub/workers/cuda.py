from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

DEFAULT_PREFERRED_GPU_NAMES = [
    "NVIDIA GeForce RTX 5090",
    "NVIDIA GeForce RTX 5070 Ti",
]


@dataclass(frozen=True)
class GpuInfo:
    index: str
    name: str
    memory_mib: int


def _parse_gpu_line(line: str) -> GpuInfo | None:
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 3:
        return None
    try:
        memory = int(parts[2])
    except ValueError:
        memory = 0
    return GpuInfo(index=parts[0], name=parts[1], memory_mib=memory)


def list_gpus() -> list[GpuInfo]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    output = []
    for line in result.stdout.splitlines():
        parsed = _parse_gpu_line(line)
        if parsed is not None:
            output.append(parsed)
    return output


def resolve_cuda_visible_devices(device: str | None) -> str | None:
    raw = (device or "auto").strip().lower()
    if raw in {"cpu", "mps"}:
        return None
    if raw.startswith("cuda:") and raw != "cuda:auto":
        return raw.split(":", 1)[1] or "0"
    if raw == "cuda":
        return "0"

    gpus = list_gpus()
    if not gpus:
        return None

    preferred_names = os.environ.get("ASUB_PREFERRED_CUDA_DEVICE_NAME")
    preferred = [preferred_names] if preferred_names else DEFAULT_PREFERRED_GPU_NAMES
    for preferred_name in preferred:
        needle = preferred_name.casefold()
        for gpu in gpus:
            if needle in gpu.name.casefold():
                return gpu.index
    return max(gpus, key=lambda gpu: gpu.memory_mib).index


def configure_cuda_environment(device: str | None) -> None:
    os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")
    if os.environ.get("CUDA_VISIBLE_DEVICES"):
        return
    visible = resolve_cuda_visible_devices(device)
    if visible is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = visible


def worker_device_map(device: str | None) -> str:
    raw = (device or "auto").strip().lower()
    if raw in {"auto", "cuda:auto"}:
        return "cuda:0"
    return device or "cuda:0"
