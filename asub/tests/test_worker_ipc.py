from pathlib import Path
import subprocess

from asub.workers import ipc
from asub.workers.ipc import WorkerClient, find_worker_python


def test_worker_client_auto_detects_project_worker_venv(monkeypatch, tmp_path):
    worker_python = tmp_path / ".venv-qwen-asr" / "bin" / "python"
    worker_python.parent.mkdir(parents=True)
    worker_python.write_text("", encoding="utf-8")
    monkeypatch.setattr(ipc, "_candidate_roots", lambda: [tmp_path])
    monkeypatch.delenv("ASUB_QWEN_ASR_PYTHON", raising=False)

    assert find_worker_python("qwen_asr") == str(worker_python)
    assert WorkerClient("qwen_asr", "asub.workers.qwen_asr_worker").command() == [
        str(worker_python),
        "-m",
        "asub.workers.qwen_asr_worker",
    ]


def test_removed_legacy_asr_workers_are_not_discovered():
    assert find_worker_python("asr") is None
    assert find_worker_python("asr" + "_" + "fp8") is None


def test_worker_client_env_override_wins(monkeypatch, tmp_path):
    override = tmp_path / "python"
    monkeypatch.setenv("ASUB_QWEN_ASR_PYTHON", str(override))
    monkeypatch.setattr(ipc, "_candidate_roots", lambda: [])

    assert WorkerClient("qwen_asr", "asub.workers.qwen_asr_worker").command()[0] == str(override)


def test_worker_client_ignores_non_json_stdout_before_response(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="WARNING noisy library output\n{\"ok\": true, \"value\": 42}\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    response = WorkerClient("qwen_asr", "asub.workers.qwen_asr_worker").call({"audio": "x.wav"})

    assert response["value"] == 42


def test_worker_client_uses_json_error_from_nonzero_worker(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=1,
            stdout='{"ok": false, "error": "CUDA out of memory"}\n',
            stderr="[worker] loading model\n",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    try:
        WorkerClient("align", "asub.workers.align_worker").call({"audio": "x.wav"})
    except Exception as exc:
        assert "CUDA out of memory" in str(exc)
    else:
        raise AssertionError("expected worker failure")
