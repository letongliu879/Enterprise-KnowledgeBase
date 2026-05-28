"""Drift guard: ensure final_doc_id does not appear as a wire property name.

Java/Python internal code may keep final_doc_id for DB columns and variables,
but wire contracts (schemas, examples, openapi) must use doc_id.
"""

from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "contracts" / "schemas"
EXAMPLE_DIR = ROOT / "contracts" / "examples"
EVENT_DIR = ROOT / "contracts" / "events"
OPENAPI_DIR = ROOT / "contracts" / "openapi"


def _schema_property_names(obj: object) -> set[str]:
    """Recursively collect all property names from a JSON schema dict."""
    names: set[str] = set()
    if not isinstance(obj, dict):
        return names
    if "properties" in obj and isinstance(obj["properties"], dict):
        for key, val in obj["properties"].items():
            names.add(key)
            names.update(_schema_property_names(val))
    if "items" in obj:
        names.update(_schema_property_names(obj["items"]))
    if "additionalProperties" in obj and isinstance(obj["additionalProperties"], dict):
        names.update(_schema_property_names(obj["additionalProperties"]))
    for key in ("allOf", "anyOf", "oneOf"):
        if key in obj and isinstance(obj[key], list):
            for item in obj[key]:
                names.update(_schema_property_names(item))
    return names


def _json_keys(obj: object) -> set[str]:
    """Recursively collect all string keys from a JSON value."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for key, val in obj.items():
            if isinstance(key, str):
                keys.add(key)
            keys.update(_json_keys(val))
    elif isinstance(obj, list):
        for item in obj:
            keys.update(_json_keys(item))
    return keys


def _yaml_keys(path: pathlib.Path) -> set[str]:
    """Naive key extraction from YAML (looks for 'key:' patterns at line start)."""
    keys: set[str] = set()
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("final_doc_id:") or stripped.startswith("doc_id:"):
            keys.add(stripped.split(":")[0].strip())
    return keys


def test_schemas_do_not_use_final_doc_id_as_property_name() -> None:
    for path in SCHEMA_DIR.glob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        names = _schema_property_names(schema)
        assert "final_doc_id" not in names, (
            f"Schema {path.name} must use 'doc_id' instead of 'final_doc_id' as property name"
        )


def test_examples_do_not_use_final_doc_id_as_key() -> None:
    for path in EXAMPLE_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        keys = _json_keys(data)
        assert "final_doc_id" not in keys, (
            f"Example {path.name} must use 'doc_id' instead of 'final_doc_id'"
        )


def test_event_schemas_do_not_use_final_doc_id_as_property_name() -> None:
    for path in EVENT_DIR.glob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        names = _schema_property_names(schema)
        assert "final_doc_id" not in names, (
            f"Event schema {path.name} must use 'doc_id' instead of 'final_doc_id'"
        )


def test_openapi_do_not_use_final_doc_id() -> None:
    for path in OPENAPI_DIR.glob("*.yaml"):
        keys = _yaml_keys(path)
        assert "final_doc_id" not in keys, (
            f"OpenAPI {path.name} must use 'doc_id' instead of 'final_doc_id'"
        )


def test_contracts_models_no_final_doc_id_wire_field() -> None:
    """Pydantic models that are wire-facing must not expose final_doc_id."""
    from reality_rag_contracts import (
        IndexProjectionPayload,
        KnowledgeContext,
        IndexBuildRequestedCommand,
    )

    wire_models = [
        IndexProjectionPayload,
        KnowledgeContext,
        IndexBuildRequestedCommand,
    ]
    for model in wire_models:
        schema = model.model_json_schema()
        names = _schema_property_names(schema)
        assert "final_doc_id" not in names, (
            f"Model {model.__name__} must use 'doc_id' instead of 'final_doc_id' on wire"
        )
