"""Helpers for the versioned extraction schema."""

from __future__ import annotations

import json
from importlib import resources
from typing import Iterable, List

SCHEMA_RESOURCE = "unifile/schema_v1.json"


def load_schema() -> dict:
    """Return the loaded JSON schema for the default output format."""
    with resources.files("unifile").joinpath("schema_v1.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def expected_columns() -> List[str]:
    """Return the ordered list of column names for schema v1."""
    schema = load_schema()
    return [c["name"] for c in schema.get("columns", [])]


def validate_columns(cols: Iterable[str]) -> bool:
    """Check that ``cols`` exactly match the schema v1 columns."""
    return list(cols) == expected_columns()
