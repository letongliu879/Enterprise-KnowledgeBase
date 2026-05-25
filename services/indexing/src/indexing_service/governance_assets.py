from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class GovernanceAssets:
    overlay: dict[str, object] = field(default_factory=dict)
    approval: dict[str, object] = field(default_factory=dict)
    document_metadata: dict[str, object] = field(default_factory=dict)


def load_governance_assets(
    *,
    governance_overlay_ref: str,
    approval_decision_ref: str,
    metadata_ref: str,
) -> GovernanceAssets:
    overlay = _load_json_file(governance_overlay_ref)
    approval = _load_json_file(approval_decision_ref)
    document_metadata = _load_json_file(metadata_ref)
    return GovernanceAssets(
        overlay=overlay if isinstance(overlay, dict) else {},
        approval=approval if isinstance(approval, dict) else {},
        document_metadata=document_metadata if isinstance(document_metadata, dict) else {},
    )


def governance_visibility(
    *,
    command_visibility: str,
    source_metadata: dict[str, str],
    overlay: dict[str, object],
) -> str:
    return str(
        overlay.get("visibility")
        or source_metadata.get("visibility")
        or command_visibility
        or "internal"
    ).strip()


def governance_confirmed_tags(
    *,
    command_tags: list[str],
    overlay: dict[str, object],
    approval: dict[str, object],
) -> list[str]:
    raw = (
        approval.get("confirmed_tags")
        or overlay.get("confirmed_tags")
        or command_tags
        or []
    )
    if not isinstance(raw, list):
        return list(command_tags or [])
    return [str(item).strip() for item in raw if str(item).strip()]


def governance_final_doc_id(
    *,
    command_final_doc_id: str,
    overlay: dict[str, object],
) -> str:
    return str(overlay.get("final_doc_id") or command_final_doc_id).strip() or command_final_doc_id


def governance_publish_version(
    *,
    command_publish_version: str,
    overlay: dict[str, object],
) -> str:
    return str(overlay.get("publish_version") or command_publish_version).strip() or command_publish_version


def governance_published_document_state(approval: dict[str, object]) -> str:
    decision = str(approval.get("decision") or "").strip().lower()
    if decision == "approve":
        return "PUBLISHED"
    if decision == "reject":
        return "REJECTED"
    return "PUBLISHED"


def governance_metadata(
    *,
    snapshot_document_metadata: dict[str, object],
    external_document_metadata: dict[str, object],
    overlay: dict[str, object],
    approval: dict[str, object],
) -> dict[str, object]:
    merged = dict(snapshot_document_metadata)
    if external_document_metadata:
        merged["governance_metadata"] = dict(external_document_metadata)
    if overlay:
        merged["governance_overlay"] = dict(overlay)
    if approval:
        merged["approval"] = dict(approval)
    return merged


def _load_json_file(ref: str) -> object:
    text = str(ref or "").strip()
    if not text:
        return {}
    path = Path(text)
    if not path.exists() or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
