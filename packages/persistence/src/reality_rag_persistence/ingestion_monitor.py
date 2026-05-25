"""File-backed ingestion monitor state shared across services."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IngestionMonitorStore:
    """Persist monitored ingestion runs as JSON + JSONL files."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        root = Path(base_dir or os.getenv("REALITY_RAG_MONITOR_DIR", ".run-logs"))
        self._base_dir = root / "ingestion-monitor"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def create_run(
        self,
        *,
        run_id: str,
        collection_id: str,
        index_version: str,
        concurrency: int,
        source_files: list[str],
    ) -> dict[str, Any]:
        now = utc_now_iso()
        run = {
            "run_id": run_id,
            "collection_id": collection_id,
            "index_version": index_version,
            "status": "pending",
            "concurrency": concurrency,
            "source_files": source_files,
            "total_files": len(source_files),
            "processed_files": 0,
            "approved_files": 0,
            "rejected_files": 0,
            "quarantined_files": 0,
            "pending_review_files": 0,
            "failed_files": 0,
            "last_seq": 0,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            run_dir = self._run_dir(run_id)
            run_dir.mkdir(parents=True, exist_ok=True)
            self._write_json(self._meta_path(run_id), run)
            events_path = self._events_path(run_id)
            if not events_path.exists():
                events_path.write_text("", encoding="utf-8")
        return run

    def update_run(self, run_id: str, **fields: Any) -> dict[str, Any]:
        with self._lock:
            run = self._read_json(self._meta_path(run_id))
            if run is None:
                raise KeyError(run_id)
            run.update(fields)
            run["updated_at"] = utc_now_iso()
            self._write_json(self._meta_path(run_id), run)
            return run

    def append_event(
        self,
        run_id: str,
        *,
        lane_id: int,
        event_type: str,
        phase: str,
        message: str,
        level: str = "info",
        source_file_path: str | None = None,
        doc_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            run = self._read_json(self._meta_path(run_id))
            if run is None:
                raise KeyError(run_id)
            seq = int(run.get("last_seq", 0)) + 1
            event = {
                "seq": seq,
                "run_id": run_id,
                "lane_id": lane_id,
                "type": event_type,
                "phase": phase,
                "level": level,
                "message": message,
                "source_file_path": source_file_path,
                "doc_id": doc_id,
                "payload": payload or {},
                "created_at": utc_now_iso(),
            }
            with self._events_path(run_id).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            run["last_seq"] = seq
            run["updated_at"] = utc_now_iso()
            self._write_json(self._meta_path(run_id), run)
            return event

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self._read_json(self._meta_path(run_id))

    def list_runs(self) -> list[dict[str, Any]]:
        runs: list[dict[str, Any]] = []
        for path in sorted(self._base_dir.glob("*/meta.json"), reverse=True):
            run = self._read_json(path)
            if run is not None:
                runs.append(run)
        runs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return runs

    def get_events(self, run_id: str, *, after_seq: int = 0) -> list[dict[str, Any]]:
        path = self._events_path(run_id)
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                event = json.loads(line)
                if int(event.get("seq", 0)) > after_seq:
                    events.append(event)
        return events

    def is_terminal(self, run_id: str) -> bool:
        run = self.get_run(run_id)
        return bool(run and run.get("status") in TERMINAL_RUN_STATUSES)

    def _run_dir(self, run_id: str) -> Path:
        return self._base_dir / run_id

    def _meta_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "meta.json"

    def _events_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "events.jsonl"

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
