from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import atexit
from dataclasses import dataclass
from typing import Any

from asub.exceptions import WorkerError

DEFAULT_WORKER_VENVS = {
    "qwen_asr": ".venv-qwen-asr",
    "mt": ".venv-mt",
    "align": ".venv-align",
}


def _scripts_python(venv: Path) -> Path:
    return venv / "Scripts" / "python.exe"


def _posix_python(venv: Path) -> Path:
    return venv / "bin" / "python"


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    for start in [Path(__file__).resolve(), Path(sys.executable).resolve()]:
        for parent in [start, *start.parents]:
            if parent not in roots:
                roots.append(parent)
    return roots


def find_worker_python(kind: str) -> str | None:
    venv_name = DEFAULT_WORKER_VENVS.get(kind)
    if not venv_name:
        return None
    for root in _candidate_roots():
        for candidate in [_scripts_python(root / venv_name), _posix_python(root / venv_name)]:
            if candidate.exists():
                return str(candidate)
    return None


def _loads_worker_response(stdout: str) -> dict[str, Any]:
    last_error: json.JSONDecodeError | None = None
    for line in stdout.splitlines():
        text = line.strip()
        if not text:
            continue
        if not text.startswith("{"):
            continue
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(loaded, dict):
            return loaded
    if last_error is not None:
        raise last_error
    raise json.JSONDecodeError("No JSON object found in worker output", stdout, 0)


def _worker_failure_detail(stdout: str, stderr: str) -> str:
    try:
        response = _loads_worker_response(stdout)
    except json.JSONDecodeError:
        return stderr.strip() or stdout.strip()
    return str(response.get("error") or stderr.strip() or stdout.strip() or "worker returned ok=false")


@dataclass
class WorkerClient:
    kind: str
    module: str

    def command(self) -> list[str]:
        override = os.environ.get(f"ASUB_{self.kind.upper()}_WORKER")
        if override:
            return [override]
        python = os.environ.get(f"ASUB_{self.kind.upper()}_PYTHON") or find_worker_python(self.kind) or sys.executable
        return [python, "-m", self.module]

    def call(self, payload: dict[str, Any], *, timeout: int | None = None) -> dict[str, Any]:
        try:
            result = subprocess.run(
                self.command(),
                input=json.dumps(payload, ensure_ascii=False),
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except OSError as exc:
            raise WorkerError(f"{self.kind} worker failed to start: {exc}") from exc
        if result.returncode != 0:
            detail = _worker_failure_detail(result.stdout, result.stderr)
            raise WorkerError(f"{self.kind} worker failed using {self.command()[0]}: {detail}")
        try:
            response = _loads_worker_response(result.stdout)
        except json.JSONDecodeError as exc:
            raise WorkerError(f"{self.kind} worker returned invalid JSON: {result.stdout[:500]}") from exc
        if not response.get("ok", False):
            detail = response.get("error") or "worker returned ok=false"
            raise WorkerError(f"{self.kind} worker failed using {self.command()[0]}: {detail}")
        return response


@dataclass
class PersistentWorkerClient(WorkerClient):
    def __post_init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._process_group_id: int | None = None
        self._lock = threading.Lock()
        atexit.register(self.close)

    def _ensure_process(self) -> subprocess.Popen[str]:
        process = getattr(self, "_process", None)
        if process is not None and process.poll() is None:
            return process
        try:
            process = subprocess.Popen(
                self.command(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,
                text=True,
                bufsize=1,
                start_new_session=os.name != "nt",
            )
        except OSError as exc:
            raise WorkerError(f"{self.kind} worker failed to start: {exc}") from exc
        self._process = process
        if os.name != "nt":
            try:
                self._process_group_id = os.getpgid(process.pid)
            except OSError:
                self._process_group_id = None
        return process

    def call(self, payload: dict[str, Any], *, timeout: int | None = None) -> dict[str, Any]:
        del timeout
        with self._lock:
            process = self._ensure_process()
            if process.stdin is None or process.stdout is None:
                raise WorkerError(f"{self.kind} worker pipes are unavailable")
            try:
                process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
                process.stdin.flush()
                line = process.stdout.readline()
            except OSError as exc:
                self.close()
                raise WorkerError(f"{self.kind} worker IPC failed: {exc}") from exc
            while line and not line.lstrip().startswith("{"):
                line = process.stdout.readline()
            if not line:
                code = process.poll()
                self.close()
                raise WorkerError(f"{self.kind} worker exited before returning a response: {code}")
            try:
                response = _loads_worker_response(line)
            except json.JSONDecodeError as exc:
                raise WorkerError(f"{self.kind} worker returned invalid JSON: {line[:500]}") from exc
            if not response.get("ok", False):
                detail = response.get("error") or "worker returned ok=false"
                raise WorkerError(f"{self.kind} worker failed using {self.command()[0]}: {detail}")
            return response

    def close(self) -> None:
        process = getattr(self, "_process", None)
        if process is None:
            return
        process_group_id = getattr(self, "_process_group_id", None)
        self._process = None
        self._process_group_id = None
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            if process.poll() is None:
                if process_group_id is not None and os.name != "nt":
                    os.killpg(process_group_id, signal.SIGTERM)
                else:
                    process.terminate()
                process.wait(timeout=5)
            elif process_group_id is not None and os.name != "nt":
                os.killpg(process_group_id, signal.SIGTERM)
        except (OSError, subprocess.TimeoutExpired):
            if process_group_id is not None and os.name != "nt":
                try:
                    os.killpg(process_group_id, signal.SIGKILL)
                except OSError:
                    pass
            else:
                process.kill()
