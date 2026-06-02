#!/usr/bin/env python3
"""
Enterprise KnowledgeBase — Local Dev Service Launcher.

One command to start all backend services in dependency order, with
colored, tagged console output. Ctrl+C stops everything cleanly.

Usage:
    py -3.14 scripts/start-services.py          # Start all services
    py -3.14 scripts/start-services.py --infra  # Start only infrastructure (docker)
    py -3.14 scripts/start-services.py --python # Start only Python services
    py -3.14 scripts/start-services.py --java   # Start only Java services
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
IS_WINDOWS = sys.platform == "win32"

# Colors for service tags
_COLORS = [
    "\033[38;5;208m",   # orange
    "\033[38;5;39m",    # cyan
    "\033[38;5;141m",   # purple
    "\033[38;5;82m",    # green
    "\033[38;5;196m",   # red
    "\033[38;5;226m",   # yellow
    "\033[38;5;51m",    # bright cyan
    "\033[38;5;213m",   # pink
    "\033[38;5;118m",   # lime
]
_RESET = "\033[0m"

# ---------------------------------------------------------------------------
# Service definitions
# ---------------------------------------------------------------------------
# Each service: name, port, cwd, cmd list, wait_for (dependency ports)
SERVICES: list[dict] = [
    {
        "name": "admin",
        "port": 18084,
        "cwd": ROOT / "services" / "admin",
        "cmd": [PYTHON, "-m", "uvicorn", "admin_service.main:app", "--host", "127.0.0.1", "--port", "18084", "--http", "h11"],
        "wait_for": [],
        "health_path": "/health",
    },
    {
        "name": "indexing",
        "port": 18080,
        "cwd": ROOT / "services" / "indexing",
        "cmd": [PYTHON, "-m", "uvicorn", "indexing_service.main:app", "--host", "127.0.0.1", "--port", "18080", "--http", "h11"],
        "wait_for": [],
        "health_path": "/health",
    },
    {
        "name": "intake-pipeline",
        "port": 18085,
        "cwd": ROOT / "services" / "intake-pipeline",
        "cmd": [PYTHON, "-m", "uvicorn", "intake_pipeline.main:app", "--host", "127.0.0.1", "--port", "18085", "--http", "h11"],
        "wait_for": [18080],  # indexing
        "health_path": "/health",
    },
    {
        "name": "publishing-worker",
        "port": 18086,
        "cwd": ROOT / "services" / "intake-pipeline" / "publishing-worker",
        "cmd": [PYTHON, "-m", "uvicorn", "publishing_worker.main:app", "--host", "127.0.0.1", "--port", "18086", "--http", "h11"],
        "wait_for": [18084, 18080],
        "health_path": "/health",
    },
    {
        "name": "approval-service",
        "port": 18087,
        "cwd": ROOT / "services" / "intake-pipeline" / "approval-service",
        "cmd": [PYTHON, "-m", "uvicorn", "approval_service.main:app", "--host", "127.0.0.1", "--port", "18087", "--http", "h11"],
        "wait_for": [18085],
        "health_path": "/health",
    },
    {
        "name": "document-service",
        "port": 8006,
        "cwd": ROOT / "services" / "intake-pipeline" / "document-service",
        "cmd": [PYTHON, "-m", "uvicorn", "document_service.main:app", "--host", "127.0.0.1", "--port", "8006", "--http", "h11"],
        "wait_for": [],
        "health_path": "/health",
    },
    {
        "name": "workbench-api",
        "port": 18083,
        "cwd": ROOT / "services" / "workbench-api",
        "cmd": [PYTHON, "-m", "uvicorn", "workbench_api.main:app", "--host", "127.0.0.1", "--port", "18083", "--http", "h11"],
        "wait_for": [18084, 18080, 18085, 18087, 8006],
        "health_path": "/workbench/health",
    },
    {
        "name": "retrieval",
        "port": 18182,
        "cwd": ROOT / "services" / "retrieval",
        "cmd": [
            "mvn", "spring-boot:run",
            "-Dspring-boot.run.arguments=--server.port=18182 --spring.profiles.active=smoke",
        ],
        "wait_for": [],
        "health_path": "/health",
        "health_timeout": 180.0,
        "shell": IS_WINDOWS,
    },
    {
        "name": "access",
        "port": 18181,
        "cwd": ROOT / "services" / "access",
        "cmd": [
            "mvn", "spring-boot:run",
            "-Dspring-boot.run.arguments=--server.port=18181 --spring.profiles.active=smoke --access.retrieval.base-url=http://127.0.0.1:18182",
        ],
        "wait_for": [18182],  # retrieval
        "health_path": "/health",
        "health_timeout": 180.0,
        "shell": IS_WINDOWS,
    },
]

PYTHON_SERVICES = ["admin", "indexing", "intake-pipeline", "publishing-worker", "approval-service", "document-service", "workbench-api"]
JAVA_SERVICES = ["retrieval", "access"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tag(name: str, color: str) -> str:
    return f"{color}[{name:>16}]{_RESET}"


def _is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _kill_process_on_port(port: int) -> bool:
    """Kill the process listening on the given port. Returns True if a process was killed."""
    pid: int | None = None
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    if parts:
                        try:
                            pid = int(parts[-1])
                            break
                        except ValueError:
                            continue
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True, timeout=5,
            )
            pid_str = result.stdout.strip()
            if pid_str:
                pid = int(pid_str)
        except Exception:
            pass

    if pid is None:
        return False

    try:
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "//PID", str(pid), "//F"],
                capture_output=True, timeout=10,
            )
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(2)
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        return True
    except Exception:
        return False


def _load_dotenv(path: Path) -> None:
    """Load KEY=value pairs from a .env file into os.environ."""
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


def _check_infra() -> list[str]:
    """Check which infrastructure ports are up."""
    infra_ports = {
        "PostgreSQL": 5432,
        "OpenSearch": 19201,
        "Qdrant": 6333,
        "Redis": 6379,
    }
    missing = []
    for name, port in infra_ports.items():
        if not _is_port_open(port):
            missing.append(f"{name} (port {port})")
    return missing


def _build_pythonpath(cwd: Path) -> str:
    """Build PYTHONPATH for a Python service."""
    srcs = [str(cwd / "src")]
    # All Python service src dirs
    for svc_name in PYTHON_SERVICES:
        svc = next(s for s in SERVICES if s["name"] == svc_name)
        srcs.append(str(svc["cwd"] / "src"))
    # Shared packages
    for pkg in ["contracts", "persistence", "documents", "ragflow_runtime"]:
        srcs.append(str(ROOT / "packages" / pkg / "src"))
    # ingestion-worker src (needed by publishing_worker imports)
    srcs.append(str(ROOT / "services" / "intake-pipeline" / "ingestion-worker" / "src"))
    existing = os.environ.get("PYTHONPATH", "")
    if existing:
        srcs.append(existing)
    return os.pathsep.join(dict.fromkeys(srcs))  # dedup while preserving order


def _stream_output(proc: subprocess.Popen, name: str, color: str, stop_event: threading.Event) -> None:
    """Read stdout/stderr from a subprocess and print with tags."""
    tag = _tag(name, color)
    streams = []
    if proc.stdout:
        streams.append(proc.stdout)
    if proc.stderr and proc.stderr != proc.stdout:
        streams.append(proc.stderr)

    while not stop_event.is_set() and proc.poll() is None:
        for stream in streams:
            try:
                line = stream.readline()
                if line:
                    text = line.decode("utf-8", errors="replace").rstrip()
                    print(f"{tag} {text}", flush=True)
            except Exception:
                pass
        time.sleep(0.05)

    # Drain remaining output
    for stream in streams:
        for line in stream:
            text = line.decode("utf-8", errors="replace").rstrip()
            print(f"{tag} {text}", flush=True)


def _wait_for_health(port: int, path: str, timeout: float = 60.0) -> bool:
    import urllib.request
    url = f"http://127.0.0.1:{port}{path}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    # Load deploy/.env so services get DATABASE_URL, JWT secrets, etc.
    _load_dotenv(ROOT / "deploy" / ".env")

    parser = argparse.ArgumentParser(description="Start EKB backend services")
    parser.add_argument("--infra", action="store_true", help="Only start docker infrastructure")
    parser.add_argument("--python", action="store_true", help="Only start Python services")
    parser.add_argument("--java", action="store_true", help="Only start Java services")
    parser.add_argument("--no-infra-check", action="store_true", help="Skip infrastructure port check")
    args = parser.parse_args()

    # Determine which services to start
    if args.infra:
        to_start = []
    elif args.python:
        to_start = [s for s in SERVICES if s["name"] in PYTHON_SERVICES]
    elif args.java:
        to_start = [s for s in SERVICES if s["name"] in JAVA_SERVICES]
    else:
        to_start = list(SERVICES)

    # Check infrastructure
    if not args.no_infra_check and (not args.python and not args.java):
        missing = _check_infra()
        if missing:
            print("\033[31mERROR: Infrastructure not ready. Missing:\033[0m")
            for m in missing:
                print(f"  - {m}")
            print("\nStart it with:")
            print("  docker compose -f deploy/docker-compose.yml up -d postgres opensearch qdrant redis")
            return 2
        else:
            print("\033[32mInfrastructure OK (PostgreSQL, OpenSearch, Qdrant, Redis)\033[0m\n")

    # Check Maven is available for Java services
    java_needed = any(s["name"] in JAVA_SERVICES for s in to_start)
    if java_needed and not shutil.which("mvn"):
        print("\033[31mERROR: Maven (mvn) not found in PATH. Cannot start Java services.\033[0m")
        return 2

    # Build color mapping
    color_map = {}
    color_idx = 0
    for svc in to_start:
        if svc["name"] not in color_map:
            color_map[svc["name"]] = _COLORS[color_idx % len(_COLORS)]
            color_idx += 1

    procs: dict[str, subprocess.Popen] = {}
    threads: list[threading.Thread] = []
    stop_event = threading.Event()

    def _shutdown(signum: int | None = None, frame: Any = None) -> None:
        """Gracefully terminate all child processes."""
        print("\n\033[33mShutting down all services...\033[0m")
        stop_event.set()
        for name, proc in list(procs.items()):
            if proc.poll() is None:
                try:
                    if IS_WINDOWS:
                        proc.terminate()
                    else:
                        proc.send_signal(signal.SIGTERM)
                except Exception:
                    pass
        # Give them 5s, then kill
        time.sleep(5)
        for name, proc in list(procs.items()):
            if proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
        print("\033[32mAll services stopped.\033[0m")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if not IS_WINDOWS:
        signal.signal(signal.SIGTERM, _shutdown)

    started_ports: set[int] = set()

    for svc in to_start:
        name = svc["name"]
        port = svc["port"]
        color = color_map[name]
        tag = _tag(name, color)

        # Wait for dependencies
        for dep_port in svc.get("wait_for", []):
            if dep_port not in started_ports:
                continue
            print(f"{tag} Waiting for dependency on port {dep_port}...", flush=True)
            deadline = time.time() + 60.0
            while time.time() < deadline:
                if _is_port_open(dep_port):
                    break
                time.sleep(0.5)
            else:
                print(f"\033[31mERROR: Dependency port {dep_port} never came up. Aborting.\033[0m")
                _shutdown()
                return 2

        # Check port not already in use
        if _is_port_open(port):
            # Port in use — verify it's actually a healthy instance of this service
            if svc.get("health_path") and _wait_for_health(port, svc["health_path"], timeout=5.0):
                print(f"{tag} Port {port} already in use and healthy, skipping.")
                started_ports.add(port)
                continue
            print(f"{tag} Port {port} already in use but not healthy — killing stale process...", flush=True)
            _kill_process_on_port(port)
            time.sleep(1)
            if _is_port_open(port):
                print(f"\033[31mERROR: Port {port} still in use after kill attempt. Aborting.\033[0m")
                _shutdown()
                return 2

        # Prepare env
        env = os.environ.copy()
        if name in PYTHON_SERVICES:
            env["PYTHONPATH"] = _build_pythonpath(svc["cwd"])

        creationflags = 0
        if IS_WINDOWS and not svc.get("shell"):
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        print(f"{tag} Starting on port {port}...", flush=True)

        try:
            proc = subprocess.Popen(
                svc["cmd"],
                cwd=svc["cwd"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                shell=svc.get("shell", False),
            )
        except Exception as e:
            print(f"\033[31mERROR: Failed to start {name}: {e}\033[0m")
            _shutdown()
            return 2

        procs[name] = proc
        started_ports.add(port)

        # Start output reader thread
        t = threading.Thread(target=_stream_output, args=(proc, name, color, stop_event), daemon=True)
        t.start()
        threads.append(t)

        # Wait for health check (except document-service which may not have a simple health endpoint)
        if svc.get("health_path"):
            print(f"{tag} Waiting for health check...", flush=True)
            healthy = _wait_for_health(port, svc["health_path"], timeout=svc.get("health_timeout", 60.0))
            if healthy:
                print(f"{tag} \033[32mHealthy on port {port}\033[0m", flush=True)
            else:
                print(f"\033[31mERROR: {name} health check timed out on port {port}\033[0m")
                _shutdown()
                return 2

    print(f"\n{'='*60}")
    print("  All services started. Press Ctrl+C to stop.")
    print(f"{'='*60}\n")

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
            # Check if any process died unexpectedly
            for name, proc in list(procs.items()):
                if proc.poll() is not None and proc.returncode != 0:
                    print(f"\033[31mWARNING: {name} exited with code {proc.returncode}\033[0m")
    except KeyboardInterrupt:
        _shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
