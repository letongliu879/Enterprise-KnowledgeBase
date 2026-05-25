from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ResolvedAsset:
    asset_ref: str
    filename: str
    suffix: str
    bytes_data: bytes


class AssetResolverPort(Protocol):
    def resolve(self, asset_ref: str) -> ResolvedAsset:
        """Resolve an asset reference into filename and bytes."""

