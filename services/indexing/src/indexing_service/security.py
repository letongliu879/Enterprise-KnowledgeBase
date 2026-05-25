from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GovernanceContext:
    tenant_id: str
    collection_id: str
    principal_id: str
    allowed_principal_ids: tuple[str, ...]
    allowed_groups: tuple[str, ...]
    visibility: str


class IndexingSecurity:
    def authorize_parse_preview(
        self,
        *,
        tenant_id: str,
        collection_id: str,
        principal_id: str,
        source_metadata: dict[str, str] | None = None,
    ) -> None:
        metadata = source_metadata or {}
        expected_tenant = metadata.get("tenant_id")
        expected_collection = metadata.get("collection_id")
        if expected_tenant and expected_tenant != tenant_id:
            raise PermissionError("tenant mismatch for parse preview")
        if expected_collection and expected_collection != collection_id:
            raise PermissionError("collection mismatch for parse preview")
        if not principal_id.strip():
            raise PermissionError("principal_id is required")

    def authorize_index_build(
        self,
        *,
        tenant_id: str,
        collection_id: str,
        source_metadata: dict[str, str],
    ) -> GovernanceContext:
        expected_tenant = source_metadata.get("tenant_id")
        expected_collection = source_metadata.get("collection_id")
        if expected_tenant and expected_tenant != tenant_id:
            raise PermissionError("tenant mismatch for index build")
        if expected_collection and expected_collection != collection_id:
            raise PermissionError("collection mismatch for index build")
        allowed_principal_ids = tuple(
            value.strip()
            for value in (source_metadata.get("allowed_principal_ids") or "").split(",")
            if value.strip()
        )
        allowed_groups = tuple(
            value.strip()
            for value in (source_metadata.get("allowed_groups") or "").split(",")
            if value.strip()
        )
        return GovernanceContext(
            tenant_id=tenant_id,
            collection_id=collection_id,
            principal_id=source_metadata.get("indexed_by") or "publishing-worker",
            allowed_principal_ids=allowed_principal_ids,
            allowed_groups=allowed_groups,
            visibility=source_metadata.get("visibility") or "internal",
        )

    def can_access_chunk(
        self,
        *,
        tenant_id: str,
        principal_id: str,
        principal_groups: tuple[str, ...],
        chunk_access_control: dict[str, list[str]],
        chunk_visibility: str,
    ) -> bool:
        if chunk_visibility == "public":
            return True
        allowed_principal_ids = set(chunk_access_control.get("allowed_principal_ids") or [])
        allowed_groups = set(chunk_access_control.get("allowed_groups") or [])
        if allowed_principal_ids and principal_id in allowed_principal_ids:
            return True
        if allowed_groups and set(principal_groups) & allowed_groups:
            return True
        return not allowed_principal_ids and not allowed_groups
