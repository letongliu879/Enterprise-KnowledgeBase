#!/usr/bin/env python3
"""
EKB Service Manager — 生产级本地开发服务守护进程。

Usage:
    py -3.14 scripts/ekb-svc.py start [--all] [--java] [--python] [--build] [--watch]
    py -3.14 scripts/ekb-svc.py stop
    py -3.14 scripts/ekb-svc.py status
    py -3.14 scripts/ekb-svc.py logs <service> [--follow]
    py -3.14 scripts/ekb-svc.py restart <service>
    py -3.14 scripts/ekb-svc.py build [--java]
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Windows Job Object (ensures child processes die with supervisor)
# ---------------------------------------------------------------------------


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_void_p),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _WinJobObject:
    """Wraps a Windows Job Object with KILL_ON_JOB_CLOSE."""

    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    _JobObjectExtendedLimitInformation = 9
    _PROCESS_ACCESS = 0x0100 | 0x0001  # PROCESS_SET_QUOTA | PROCESS_TERMINATE

    def __init__(self) -> None:
        self._handle: int | None = None
        if not IS_WINDOWS:
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = self._JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = kernel32.SetInformationJobObject(
            handle,
            self._JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not ok:
            kernel32.CloseHandle(handle)
            raise ctypes.WinError(ctypes.get_last_error())
        self._handle = handle
        self._kernel32 = kernel32

    def assign(self, pid: int) -> bool:
        """Assign a process to this job. Best-effort."""
        if self._handle is None:
            return False
        handle = self._kernel32.OpenProcess(self._PROCESS_ACCESS, False, pid)
        if not handle:
            return False
        try:
            ok = self._kernel32.AssignProcessToJobObject(self._handle, handle)
            return bool(ok)
        finally:
            self._kernel32.CloseHandle(handle)

    def close(self) -> None:
        """Close the job handle. On Windows this kills all processes in the job."""
        if self._handle is not None:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
IS_WINDOWS = sys.platform == "win32"
PID_DIR = ROOT / "tmp" / "run"
SUPERVISOR_PID_PATH = PID_DIR / "supervisor.pid"


def _find_maven() -> str | None:
    mvn = shutil.which("mvn")
    if mvn:
        return mvn
    # Fallback to bundled Maven
    bundled = ROOT / "tools" / "apache-maven-3.9.16" / "bin" / ("mvn.cmd" if IS_WINDOWS else "mvn")
    if bundled.exists():
        return str(bundled)
    return None


MAVEN_CMD = _find_maven()
LOG_DIR = ROOT / "tmp" / "services"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_LOG_BACKUPS = 3
RESTART_MAX_RETRIES = 5
RESTART_BACKOFF_BASE = 1.0
CHECK_INTERVAL = 1.0  # seconds between supervisor checks

_COLORS = {
    "green": "\033[32m",
    "red": "\033[31m",
    "yellow": "\033[33m",
    "cyan": "\033[36m",
    "dim": "\033[2m",
    "reset": "\033[0m",
}

# ---------------------------------------------------------------------------
# Service definitions
# ---------------------------------------------------------------------------
# NOTE: ingestion-worker src is also on PYTHONPATH for publishing-worker / agent-review-worker / conversion-worker
_BASE_PYTHONPATH_DIRS = [
    ROOT / "packages" / "contracts" / "src",
    ROOT / "packages" / "persistence" / "src",
    ROOT / "packages" / "documents" / "src",
    ROOT / "packages" / "ragflow_runtime" / "src",
]


def _pp(*parts: Path) -> str:
    return os.pathsep.join(str(p) for p in parts)


PYTHON_SERVICES: list[dict[str, Any]] = [  # each must include "language": "python"
    {
        "language": "python",
        "name": "admin",
        "port": 18084,
        "cwd": ROOT / "services" / "admin",
        "cmd": [PYTHON, "-m", "uvicorn", "admin_service.main:app", "--host", "127.0.0.1", "--port", "18084", "--http", "h11"],
        "depends_on": [],
        "health_path": "/health",
        "health_timeout": 60.0,
        "reload_dirs": [ROOT / "services" / "admin" / "src"],
    },
    {
        "language": "python",
        "name": "indexing",
        "port": 18080,
        "cwd": ROOT / "services" / "indexing",
        "cmd": [PYTHON, "-m", "uvicorn", "indexing_service.main:app", "--host", "127.0.0.1", "--port", "18080", "--http", "h11"],
        "depends_on": [],
        "health_path": "/health",
        "health_timeout": 60.0,
        "reload_dirs": [ROOT / "services" / "indexing" / "src"],
    },
    {
        "language": "python",
        "name": "document-service",
        "port": 8006,
        "cwd": ROOT / "services" / "intake-pipeline" / "document-service",
        "cmd": [PYTHON, "-m", "uvicorn", "document_service.main:app", "--host", "127.0.0.1", "--port", "8006", "--http", "h11"],
        "depends_on": [],
        "health_path": "/health",
        "health_timeout": 60.0,
        "reload_dirs": [ROOT / "services" / "intake-pipeline" / "document-service" / "src"],
    },
    {
        "language": "python",
        "name": "intake-pipeline",
        "port": 18085,
        "cwd": ROOT / "services" / "intake-pipeline",
        "cmd": [PYTHON, "-m", "uvicorn", "intake_pipeline.main:app", "--host", "127.0.0.1", "--port", "18085", "--http", "h11"],
        "depends_on": ["indexing"],
        "health_path": "/health",
        "health_timeout": 60.0,
        "reload_dirs": [ROOT / "services" / "intake-pipeline" / "src"],
    },
    {
        "language": "python",
        "name": "publishing-worker",
        "port": 18086,
        "cwd": ROOT / "services" / "intake-pipeline" / "publishing-worker",
        "cmd": [PYTHON, "-m", "uvicorn", "publishing_worker.main:app", "--host", "127.0.0.1", "--port", "18086", "--http", "h11"],
        "depends_on": ["admin", "indexing"],
        "health_path": "/health",
        "health_timeout": 60.0,
        "reload_dirs": [
            ROOT / "services" / "intake-pipeline" / "publishing-worker" / "src",
            ROOT / "services" / "intake-pipeline" / "ingestion-worker" / "src",
        ],
    },
    {
        "language": "python",
        "name": "approval-service",
        "port": 18087,
        "cwd": ROOT / "services" / "intake-pipeline" / "approval-service",
        "cmd": [PYTHON, "-m", "uvicorn", "approval_service.main:app", "--host", "127.0.0.1", "--port", "18087", "--http", "h11"],
        "depends_on": ["intake-pipeline"],
        "health_path": "/health",
        "health_timeout": 60.0,
        "reload_dirs": [ROOT / "services" / "intake-pipeline" / "approval-service" / "src"],
    },
    {
        "language": "python",
        "name": "agent-review-worker",
        "port": 18090,
        "cwd": ROOT / "services" / "intake-pipeline" / "agent-review-worker",
        "cmd": [PYTHON, "-m", "uvicorn", "agent_review_worker.main:app", "--host", "127.0.0.1", "--port", "18090", "--http", "h11"],
        "depends_on": ["intake-pipeline"],
        "health_path": "/health",
        "health_timeout": 60.0,
        "reload_dirs": [
            ROOT / "services" / "intake-pipeline" / "agent-review-worker" / "src",
            ROOT / "services" / "intake-pipeline" / "ingestion-worker" / "src",
        ],
    },
    {
        "language": "python",
        "name": "conversion-worker",
        "port": 18089,
        "cwd": ROOT / "services" / "intake-pipeline" / "conversion-worker",
        "cmd": [PYTHON, "-m", "uvicorn", "conversion_worker.main:app", "--host", "127.0.0.1", "--port", "18089", "--http", "h11"],
        "depends_on": ["indexing"],
        "health_path": "/health",
        "health_timeout": 60.0,
        "reload_dirs": [
            ROOT / "services" / "intake-pipeline" / "conversion-worker" / "src",
            ROOT / "services" / "intake-pipeline" / "ingestion-worker" / "src",
        ],
    },
    {
        "language": "python",
        "name": "ingestion-worker",
        "port": 18088,
        "cwd": ROOT / "services" / "intake-pipeline" / "ingestion-worker",
        "cmd": [PYTHON, "-m", "uvicorn", "ingestion_worker.main:app", "--host", "127.0.0.1", "--port", "18088", "--http", "h11"],
        "depends_on": ["indexing", "approval-service", "document-service"],
        "health_path": "/health",
        "health_timeout": 60.0,
        "reload_dirs": [ROOT / "services" / "intake-pipeline" / "ingestion-worker" / "src"],
    },
    {
        "language": "python",
        "name": "workbench-api",
        "port": 18083,
        "cwd": ROOT / "services" / "workbench-api",
        "cmd": [PYTHON, "-m", "uvicorn", "workbench_api.main:app", "--host", "127.0.0.1", "--port", "18083", "--http", "h11"],
        "depends_on": ["admin", "indexing", "intake-pipeline", "approval-service", "document-service"],
        "health_path": "/workbench/health",
        "health_timeout": 60.0,
        "reload_dirs": [ROOT / "services" / "workbench-api" / "src"],
    },
]

JAVA_SERVICES: list[dict[str, Any]] = [  # each must include "language": "java"
    {
        "language": "java",
        "name": "retrieval",
        "port": 18182,
        "cwd": ROOT / "services" / "retrieval",
        "jar_pattern": "target/retrieval-*.jar",
        "jvm_args": ["-Dspring.profiles.active=smoke", "-Dserver.port=18182"],
        "build_cmd": [MAVEN_CMD or "mvn", "package", "-DskipTests"],
        "depends_on": [],
        "health_path": "/health",
        "health_timeout": 60.0,
    },
    {
        "language": "java",
        "name": "access",
        "port": 18181,
        "cwd": ROOT / "services" / "access",
        "jar_pattern": "target/access-*.jar",
        "jvm_args": [
            "-Dspring.profiles.active=smoke",
            "-Dserver.port=18181",
            "-Daccess.retrieval.base-url=http://127.0.0.1:18182",
        ],
        "build_cmd": [MAVEN_CMD or "mvn", "package", "-DskipTests"],
        "depends_on": ["retrieval"],
        "health_path": "/health",
        "health_timeout": 60.0,
    },
]

ALL_SERVICES = PYTHON_SERVICES + JAVA_SERVICES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _color(key: str, text: str) -> str:
    return f"{_COLORS.get(key, '')}{text}{_COLORS['reset']}"


def _tag(name: str) -> str:
    return f"[{name:>18}]"


def _is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _ensure_dirs() -> None:
    PID_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _log_path(name: str, stream: str) -> Path:
    return LOG_DIR / f"{name}.{stream}.log"


def _pid_path(name: str) -> Path:
    return PID_DIR / f"{name}.pid"


def _write_pid(name: str, pid: int) -> None:
    _pid_path(name).write_text(str(pid), encoding="utf-8")


def _read_pid(name: str) -> int | None:
    p = _pid_path(name)
    if not p.exists():
        return None
    try:
        return int(p.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _remove_pid(name: str) -> None:
    try:
        _pid_path(name).unlink()
    except Exception:
        pass


def _is_process_alive(pid: int) -> bool:
    if not pid:
        return False
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                f'tasklist /FI "PID eq {pid}" /NH',
                capture_output=True, text=True, timeout=2, shell=True,
            )
            return str(pid) in result.stdout
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _kill_process(pid: int, _graceful_timeout: float = 5.0) -> bool:
    """Kill a process by PID. Best-effort on Windows (no blocking checks)."""
    if pid is None:
        return True
    try:
        if IS_WINDOWS:
            subprocess.run(
                f'taskkill /PID {pid} /T /F',
                capture_output=True, timeout=5, shell=True,
            )
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        return True
    except Exception:
        return False


def _rotate_log(path: Path) -> None:
    """Rotate log file if it exceeds MAX_LOG_SIZE."""
    if not path.exists() or path.stat().st_size < MAX_LOG_SIZE:
        return
    # Remove oldest backup
    oldest = path.with_suffix(f".log.{MAX_LOG_BACKUPS}")
    if oldest.exists():
        oldest.unlink()
    # Shift existing backups
    for i in range(MAX_LOG_BACKUPS - 1, 0, -1):
        src = path.with_suffix(f".log.{i}")
        dst = path.with_suffix(f".log.{i + 1}")
        if src.exists():
            src.rename(dst)
    # Rotate current
    path.rename(path.with_suffix(".log.1"))


def _build_pythonpath(svc: dict[str, Any]) -> str:
    dirs = list(_BASE_PYTHONPATH_DIRS)
    # Service own src
    dirs.append(svc["cwd"] / "src")
    # Add all other Python service src dirs (for cross-imports)
    for s in PYTHON_SERVICES:
        dirs.append(s["cwd"] / "src")
    # ingestion-worker src needed by publishing-worker / agent-review-worker / conversion-worker
    dirs.append(ROOT / "services" / "intake-pipeline" / "ingestion-worker" / "src")
    existing = os.environ.get("PYTHONPATH", "")
    if existing:
        for part in existing.split(os.pathsep):
            dirs.append(Path(part))
    seen = set()
    unique = []
    for d in dirs:
        p = str(d)
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return os.pathsep.join(unique)


def _topo_sort(services: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Return list of layers, each layer can be started in parallel."""
    name_to_svc = {s["name"]: s for s in services}
    in_degree = {s["name"]: 0 for s in services}
    adj = {s["name"]: [] for s in services}
    for s in services:
        for dep in s.get("depends_on", []):
            if dep in name_to_svc:
                in_degree[s["name"]] += 1
                adj[dep].append(s["name"])
    layers = []
    while in_degree:
        layer = [name for name, deg in in_degree.items() if deg == 0]
        if not layer:
            raise RuntimeError("Circular dependency detected among services")
        layers.append([name_to_svc[n] for n in layer])
        for name in layer:
            del in_degree[name]
            for downstream in adj[name]:
                in_degree[downstream] -= 1
    return layers


def _health_check(port: int, path: str, timeout: float = 60.0) -> tuple[bool, str]:
    """Three-phase health check: (1) port open (2) HTTP reachable (3) HTTP 200.
    Returns (ok, status_msg).
    """
    url = f"http://127.0.0.1:{port}{path}"
    deadline = time.time() + timeout
    port_opened = False
    while time.time() < deadline:
        if _is_port_open(port):
            port_opened = True
            break
        time.sleep(0.5)
    if not port_opened:
        return False, f"port {port} not open after {timeout:.0f}s"

    http_deadline = time.time() + min(timeout, 30.0)
    while time.time() < http_deadline:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    return True, "healthy"
                return False, f"HTTP {resp.status}"
        except urllib.error.HTTPError as e:
            if e.code in (503, 502):
                # Spring Boot starting up
                time.sleep(0.5)
                continue
            return False, f"HTTP {e.code}"
        except Exception:
            time.sleep(0.5)
    return False, "HTTP unreachable"


def _tail_lines(path: Path, n: int = 30) -> list[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-n:] if len(lines) > n else lines
    except Exception:
        return []


def _find_jar(cwd: Path, pattern: str) -> Path | None:
    candidates = list(cwd.glob(pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _needs_build(svc: dict[str, Any]) -> bool:
    jar = _find_jar(svc["cwd"], svc["jar_pattern"])
    if jar is None:
        return True
    jar_mtime = jar.stat().st_mtime
    pom = svc["cwd"] / "pom.xml"
    src = svc["cwd"] / "src"
    if pom.exists() and pom.stat().st_mtime > jar_mtime:
        return True
    if src.exists():
        for f in src.rglob("*"):
            if f.is_file() and f.stat().st_mtime > jar_mtime:
                return True
    return False


def _build_java_service(svc: dict[str, Any]) -> bool:
    print(_color("cyan", _tag("build")), f"Building {svc['name']} ...")
    out_log = _log_path(svc["name"], "build.out")
    err_log = _log_path(svc["name"], "build.err")
    _rotate_log(out_log)
    _rotate_log(err_log)
    build_cmd = [MAVEN_CMD or "mvn"] + svc["build_cmd"][1:]
    with open(out_log, "wb") as out_f, open(err_log, "wb") as err_f:
        proc = subprocess.Popen(
            build_cmd,
            cwd=svc["cwd"],
            stdout=out_f,
            stderr=err_f,
        )
        try:
            rc = proc.wait(timeout=300.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            print(_color("red", _tag("build")), f"{svc['name']} build timed out after 300s")
            return False
    if rc != 0:
        print(_color("red", _tag("build")), f"{svc['name']} build failed (exit {rc})")
        print(_color("dim", "Last lines from build.err:"))
        for line in _tail_lines(err_log, 20):
            print("  ", line)
        return False
    print(_color("green", _tag("build")), f"{svc['name']} built successfully")
    return True


class _ServiceHandle:
    """Holds process and open file handles for a service."""
    def __init__(self, proc: subprocess.Popen, out_f, err_f):
        self.proc = proc
        self.out_f = out_f
        self.err_f = err_f


def _start_service(svc: dict[str, Any], reload: bool = False, job: _WinJobObject | None = None) -> _ServiceHandle | None:
    name = svc["name"]
    port = svc["port"]

    # Check for stale PID
    old_pid = _read_pid(name)
    if old_pid is not None and _is_process_alive(old_pid):
        if _is_port_open(port):
            ok, msg = _health_check(port, svc["health_path"], timeout=5.0)
            if ok:
                print(_color("yellow", _tag(name)), f"Already running and healthy (pid {old_pid})")
                return None
        print(_color("yellow", _tag(name)), f"Killing stale process (pid {old_pid})")
        _kill_process(old_pid)
    _remove_pid(name)

    # Kill any process on port (last resort)
    if _is_port_open(port):
        print(_color("yellow", _tag(name)), f"Port {port} in use, attempting cleanup...")
        time.sleep(1)
        if _is_port_open(port):
            print(_color("red", _tag(name)), f"Port {port} still in use, cannot start")
            return None

    # Rotate logs
    out_log = _log_path(name, "out")
    err_log = _log_path(name, "err")
    _rotate_log(out_log)
    _rotate_log(err_log)

    env = os.environ.copy()
    if svc.get("language") == "python":
        env["PYTHONPATH"] = _build_pythonpath(svc)
        cmd = list(svc["cmd"])
        if reload:
            cmd.append("--reload")
            for d in svc.get("reload_dirs", []):
                cmd.extend(["--reload-dir", str(d)])
    else:
        jar = _find_jar(svc["cwd"], svc["jar_pattern"])
        if jar is None:
            print(_color("red", _tag(name)), "No jar found. Run 'build' first.")
            return None
        cmd = ["java"] + svc.get("jvm_args", []) + ["-jar", str(jar)]

    out_f = open(out_log, "ab")
    err_f = open(err_log, "ab")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=svc["cwd"],
            env=env,
            stdout=out_f,
            stderr=err_f,
        )
    except Exception as e:
        out_f.close()
        err_f.close()
        print(_color("red", _tag(name)), f"Failed to start: {e}")
        return None

    # Windows: assign child to Job Object so it dies with supervisor
    if IS_WINDOWS and job is not None:
        if not job.assign(proc.pid):
            print(_color("yellow", _tag(name)), "Warning: could not assign to Job Object")

    _write_pid(name, proc.pid)
    print(_color("cyan", _tag(name)), f"Started (pid {proc.pid}) on port {port}")
    return _ServiceHandle(proc, out_f, err_f)


def _kill_process_on_port(port: int) -> bool:
    """Find and kill process listening on given port (Windows only)."""
    if not IS_WINDOWS:
        return False
    try:
        result = subprocess.run(
            f'netstat -ano | findstr ":{port}"',
            capture_output=True, text=True, timeout=5, shell=True,
        )
        for line in result.stdout.splitlines():
            if "LISTENING" in line:
                parts = line.strip().split()
                if parts:
                    try:
                        pid = int(parts[-1])
                        return _kill_process(pid)
                    except ValueError:
                        continue
    except Exception:
        pass
    return False


def _stop_service(svc: dict[str, Any]) -> bool:
    name = svc["name"]
    port = svc["port"]
    pid = _read_pid(name)
    if pid is not None:
        _kill_process(pid)
        print(_color("green", _tag(name)), "Stopped")
    else:
        print(_color("dim", _tag(name)), "Not running")
    _remove_pid(name)
    return True


# ---------------------------------------------------------------------------
# Supervisor loop
# ---------------------------------------------------------------------------

class Supervisor:
    def __init__(self, services: list[dict[str, Any]], reload: bool = False):
        self.services = {s["name"]: s for s in services}
        self.procs: dict[str, subprocess.Popen] = {}
        self.reload = reload
        self.shutdown_event = threading.Event()
        self.restart_counts: dict[str, int] = {s["name"]: 0 for s in services}
        self.backoff_until: dict[str, float] = {}
        self._job = _WinJobObject()

    def start_all(self) -> bool:
        # Write supervisor PID so 'stop' can find us
        try:
            SUPERVISOR_PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
        except Exception:
            pass
        layers = _topo_sort(list(self.services.values()))
        for layer in layers:
            # Start layer in parallel
            with ThreadPoolExecutor(max_workers=len(layer)) as exe:
                futures = {}
                for svc in layer:
                    if self.shutdown_event.is_set():
                        return False
                    fut = exe.submit(self._start_and_health, svc)
                    futures[fut] = svc["name"]
                for fut in as_completed(futures):
                    name = futures[fut]
                    try:
                        ok = fut.result()
                    except Exception as e:
                        print(_color("red", _tag(name)), f"Exception during start: {e}")
                        ok = False
                    if not ok:
                        print(_color("red", _tag(name)), "Failed to start. Initiating shutdown...")
                        self.shutdown()
                        return False
        return True

    def _start_and_health(self, svc: dict[str, Any]) -> bool:
        name = svc["name"]
        handle = _start_service(svc, reload=self.reload, job=self._job)
        if handle is None:
            # Already running and healthy
            return True
        self.procs[name] = handle

        print(_color("cyan", _tag(name)), "Waiting for health check...")
        ok, msg = _health_check(svc["port"], svc["health_path"], timeout=svc.get("health_timeout", 60.0))
        if ok:
            print(_color("green", _tag(name)), f"Healthy on port {svc['port']}")
            self.restart_counts[name] = 0
            return True
        print(_color("red", _tag(name)), f"Health check failed: {msg}")
        out_log = _log_path(name, "out")
        err_log = _log_path(name, "err")
        for label, path in [("stdout", out_log), ("stderr", err_log)]:
            lines = _tail_lines(path, 30)
            if lines:
                print(_color("dim", f"  Last {len(lines)} lines of {label}:"))
                for line in lines:
                    print(_color("dim", f"    {line}"))
        return False

    def run(self) -> None:
        print(_color("green", "=" * 60))
        print(_color("green", "  All services started. Supervisor running."))
        print(_color("green", "  Press Ctrl+C to stop gracefully."))
        print(_color("green", "=" * 60))
        try:
            while not self.shutdown_event.is_set():
                self._check_services()
                time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def _check_services(self) -> None:
        now = time.time()
        for name, svc in self.services.items():
            if self.shutdown_event.is_set():
                return
            handle = self.procs.get(name)
            if handle is None:
                # Might have been started by a previous layer but marked None (already running)
                pid = _read_pid(name)
                if pid is None or not _is_process_alive(pid):
                    # Process died without us knowing
                    if now < self.backoff_until.get(name, 0):
                        continue
                    if self.restart_counts[name] >= RESTART_MAX_RETRIES:
                        print(_color("red", _tag(name)), f"Exceeded max restarts ({RESTART_MAX_RETRIES}), giving up.")
                        continue
                    self.restart_counts[name] += 1
                    backoff = RESTART_BACKOFF_BASE * (2 ** (self.restart_counts[name] - 1))
                    print(_color("yellow", _tag(name)), f"Process missing, restarting (attempt {self.restart_counts[name]}, backoff {backoff:.0f}s)...")
                    self.backoff_until[name] = now + backoff
                    ok = self._start_and_health(svc)
                    if not ok:
                        print(_color("red", _tag(name)), "Restart failed")
                continue

            # Check if process exited
            ret = handle.proc.poll()
            if ret is not None:
                print(_color("red", _tag(name)), f"Exited with code {ret}")
                handle.out_f.close()
                handle.err_f.close()
                self.procs[name] = None
                _remove_pid(name)
                if now < self.backoff_until.get(name, 0):
                    continue
                if self.restart_counts[name] >= RESTART_MAX_RETRIES:
                    print(_color("red", _tag(name)), f"Exceeded max restarts ({RESTART_MAX_RETRIES}), giving up.")
                    continue
                self.restart_counts[name] += 1
                backoff = RESTART_BACKOFF_BASE * (2 ** (self.restart_counts[name] - 1))
                print(_color("yellow", _tag(name)), f"Restarting in {backoff:.0f}s (attempt {self.restart_counts[name]})...")
                self.backoff_until[name] = now + backoff
                ok = self._start_and_health(svc)
                if not ok:
                    print(_color("red", _tag(name)), "Restart failed")

    def shutdown(self) -> None:
        if self.shutdown_event.is_set():
            return
        self.shutdown_event.set()
        print(_color("yellow", "\nShutting down all services..."))
        # Close file handles first
        for handle in self.procs.values():
            if handle is not None:
                try:
                    handle.out_f.close()
                except Exception:
                    pass
                try:
                    handle.err_f.close()
                except Exception:
                    pass
        # Stop in reverse dependency order
        layers = _topo_sort(list(self.services.values()))
        for layer in reversed(layers):
            for svc in layer:
                _stop_service(svc)
        # Closing the Job Object kills any remaining children on Windows
        self._job.close()
        try:
            SUPERVISOR_PID_PATH.unlink()
        except Exception:
            pass
        print(_color("green", "All services stopped."))


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def _select_services(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.java:
        return list(JAVA_SERVICES)
    if args.python:
        return list(PYTHON_SERVICES)
    return list(ALL_SERVICES)


def cmd_start(args: argparse.Namespace) -> int:
    _load_dotenv(ROOT / "deploy" / ".env")
    _ensure_dirs()
    services = _select_services(args)

    # Build Java services if needed
    java_svcs = [s for s in services if s.get("language") != "python"]
    if java_svcs and not args.no_build:
        for svc in java_svcs:
            if _needs_build(svc):
                if not _build_java_service(svc):
                    return 2

    # Check infrastructure
    if not args.no_infra_check:
        infra = {"PostgreSQL": 5432, "OpenSearch": 19201, "Qdrant": 6333, "Redis": 6379}
        missing = [f"{n} (port {p})" for n, p in infra.items() if not _is_port_open(p)]
        if missing:
            print(_color("red", "ERROR: Infrastructure not ready:"))
            for m in missing:
                print(f"  - {m}")
            print("\nStart it with:")
            print("  docker compose -f deploy/docker-compose.yml up -d postgres opensearch qdrant redis")
            return 2
        print(_color("green", "Infrastructure OK (PostgreSQL, OpenSearch, Qdrant, Redis)\n"))

    # Check Maven
    if java_svcs and not MAVEN_CMD:
        print(_color("red", "ERROR: Maven (mvn) not found in PATH or tools/."))
        return 2

    sup = Supervisor(services, reload=args.watch)
    if not sup.start_all():
        return 2
    sup.run()
    return 0


def _kill_other_supervisors() -> None:
    """Kill any other ekb-svc.py start processes so they don't restart services."""
    # Rely on supervisor PID file rather than scanning all processes
    # (Windows process scanning is slow and unreliable in Git Bash)
    sup_pid = _read_pid("supervisor")
    if sup_pid is not None and sup_pid != os.getpid():
        print(_color("yellow", _tag("stop")), f"Killing supervisor (pid {sup_pid})")
        _kill_process(sup_pid)
        try:
            SUPERVISOR_PID_PATH.unlink()
        except Exception:
            pass


def cmd_stop(_args: argparse.Namespace) -> int:
    _ensure_dirs()
    # First, kill any running supervisor so it doesn't restart services
    _kill_other_supervisors()
    # Stop all services in reverse dependency order
    layers = _topo_sort(list(ALL_SERVICES))
    for layer in reversed(layers):
        for svc in layer:
            _stop_service(svc)
    time.sleep(2)
    # Second pass: only services still alive (catches stragglers)
    for svc in ALL_SERVICES:
        pid = _read_pid(svc["name"])
        if pid is not None and _is_process_alive(pid):
            _stop_service(svc)
    # Quick port sweep — log only, don't block
    open_ports = [(s["name"], s["port"]) for s in ALL_SERVICES if _is_port_open(s["port"])]
    if open_ports:
        print(_color("yellow", _tag("stop")), "Some ports still open (services may need manual cleanup):")
        for name, port in open_ports:
            print(f"  - {name} on port {port}")
    print(_color("green", "Done."))
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    _ensure_dirs()
    print(f"{'Service':<20} {'PID':>8} {'Port':>6} {'Status':<12} {'Health':<20}")
    print("-" * 70)
    for svc in ALL_SERVICES:
        name = svc["name"]
        pid = _read_pid(name)
        port = svc["port"]
        alive = _kill_process(pid) is False if pid else False  # hack: _kill_process returns False on failure
        port_open = _is_port_open(port)
        status = "running" if alive else "stopped"
        health = "—"
        if alive and port_open:
            ok, msg = _health_check(port, svc["health_path"], timeout=3.0)
            health = "healthy" if ok else msg
        elif alive and not port_open:
            health = "port closed"
        print(f"{name:<20} {pid or '-':>8} {port:>6} {status:<12} {health:<20}")
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    name = args.service
    paths = [_log_path(name, "out"), _log_path(name, "err")]
    if not any(p.exists() for p in paths):
        print(_color("red", f"No logs found for {name}"))
        return 1
    if args.follow:
        print(_color("yellow", f"Tailing logs for {name} (Ctrl+C to stop)..."))
        positions = {p: p.stat().st_size for p in paths if p.exists()}
        try:
            while True:
                for p in paths:
                    if not p.exists():
                        continue
                    current = p.stat().st_size
                    pos = positions.get(p, 0)
                    if current > pos:
                        with open(p, "rb") as f:
                            f.seek(pos)
                            data = f.read(current - pos)
                            stream = "out" if ".out." in p.name else "err"
                            for line in data.decode("utf-8", errors="replace").splitlines():
                                print(f"[{stream}] {line}")
                        positions[p] = current
                time.sleep(0.5)
        except KeyboardInterrupt:
            print()
    else:
        for p in paths:
            if p.exists():
                stream = "out" if p.suffix == ".out.log" else "err"
                print(_color("cyan", f"--- {stream} ---"))
                for line in _tail_lines(p, 50):
                    print(line)
    return 0


def cmd_restart(args: argparse.Namespace) -> int:
    name = args.service
    svc = next((s for s in ALL_SERVICES if s["name"] == name), None)
    if svc is None:
        print(_color("red", f"Unknown service: {name}"))
        return 2
    _load_dotenv(ROOT / "deploy" / ".env")
    _ensure_dirs()
    if svc.get("language") != "python" and _needs_build(svc):
        if not _build_java_service(svc):
            return 2
    _stop_service(svc)
    time.sleep(1)
    proc = _start_service(svc, job=None)
    if proc is False:
        return 2
    if proc is None:
        return 0
    ok, msg = _health_check(svc["port"], svc["health_path"], timeout=svc.get("health_timeout", 60.0))
    if ok:
        print(_color("green", _tag(name)), "Restarted and healthy")
        return 0
    print(_color("red", _tag(name)), f"Health check failed: {msg}")
    return 2


def cmd_build(args: argparse.Namespace) -> int:
    services = list(JAVA_SERVICES) if args.java else list(ALL_SERVICES)
    java_svcs = [s for s in services if s.get("language") != "python"]
    if not java_svcs:
        print(_color("yellow", "No Java services to build."))
        return 0
    if not MAVEN_CMD:
        print(_color("red", "ERROR: Maven (mvn) not found in PATH or tools/."))
        return 2
    _ensure_dirs()
    ok_all = True
    for svc in java_svcs:
        if not _build_java_service(svc):
            ok_all = False
    return 0 if ok_all else 2


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="EKB Service Manager")
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="Start services")
    p_start.add_argument("--java", action="store_true", help="Only Java services")
    p_start.add_argument("--python", action="store_true", help="Only Python services")
    p_start.add_argument("--no-build", action="store_true", help="Skip Java build check")
    p_start.add_argument("--no-infra-check", action="store_true", help="Skip infrastructure check")
    p_start.add_argument("--watch", action="store_true", help="Enable Python --reload")

    sub.add_parser("stop", help="Stop all services")
    sub.add_parser("status", help="Show service status")

    p_logs = sub.add_parser("logs", help="Show service logs")
    p_logs.add_argument("service", help="Service name")
    p_logs.add_argument("-f", "--follow", action="store_true", help="Follow log output")

    p_restart = sub.add_parser("restart", help="Restart a service")
    p_restart.add_argument("service", help="Service name")

    p_build = sub.add_parser("build", help="Build Java services")
    p_build.add_argument("--java", action="store_true", help="Build Java services")

    args = parser.parse_args()

    handlers = {
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "logs": cmd_logs,
        "restart": cmd_restart,
        "build": cmd_build,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
