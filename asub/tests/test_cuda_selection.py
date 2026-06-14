import os
import subprocess

from asub.workers import cuda


def test_auto_device_prefers_5090(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=(
                "0, NVIDIA GeForce RTX 5070 Ti, 16303\n"
                "1, NVIDIA GeForce RTX 5090, 32607\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert cuda.resolve_cuda_visible_devices("auto") == "1"


def test_auto_device_prefers_5070_ti_when_5090_is_absent(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=(
                "0, NVIDIA GeForce RTX 3080, 10240\n"
                "1, NVIDIA GeForce RTX 5070 Ti, 16303\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert cuda.resolve_cuda_visible_devices("auto") == "1"


def test_auto_device_falls_back_to_largest_gpu(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=(
                "0, NVIDIA GeForce RTX 3080, 10240\n"
                "1, NVIDIA GeForce RTX 4090, 24576\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("ASUB_PREFERRED_CUDA_DEVICE_NAME", "NVIDIA GeForce RTX 5070 Ti")

    assert cuda.resolve_cuda_visible_devices("auto") == "1"


def test_explicit_cuda_index_is_preserved(monkeypatch):
    assert cuda.resolve_cuda_visible_devices("cuda:0") == "0"
    assert cuda.resolve_cuda_visible_devices("cuda:1") == "1"


def test_configure_cuda_environment_sets_order_and_visible_device(monkeypatch):
    monkeypatch.delenv("CUDA_DEVICE_ORDER", raising=False)
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.setattr(cuda, "resolve_cuda_visible_devices", lambda device: "1")

    cuda.configure_cuda_environment("auto")

    assert os.environ["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"
    assert os.environ["CUDA_VISIBLE_DEVICES"] == "1"
