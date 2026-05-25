from __future__ import annotations

from pathlib import Path

from ragflow_runtime.ports.asset_resolver import AssetResolverPort, ResolvedAsset


class LocalAssetResolver(AssetResolverPort):
    def resolve(self, asset_ref: str) -> ResolvedAsset:
        path = Path(asset_ref.removeprefix("file://")) if asset_ref.startswith("file://") else Path(asset_ref)
        return ResolvedAsset(
            asset_ref=asset_ref,
            filename=path.name,
            suffix=path.suffix.lower().lstrip("."),
            bytes_data=path.read_bytes(),
        )

