# Copyright (c) 2025 takotime808

from __future__ import annotations

from pathlib import Path
from typing import List
import json

from unifile.extractors.base import (
    BaseExtractor,
    make_row,
    Row,
)


def _flatten(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _flatten(v, f"{prefix}{k}.")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _flatten(v, f"{prefix}{i}.")
    else:
        yield prefix[:-1], obj


class JsonExtractor(BaseExtractor):
    """JSON/NDJSON --> text lines ('key=value') for easy search; one row per file."""
    supported_extensions = ["json"]

    def _extract(self, path: Path) -> List[Row]:
        txt = path.read_text(errors="replace").strip()
        # NDJSON quickly?
        if "\n" in txt and txt.lstrip().startswith("{"):
            return [make_row(path, "json", "file", "body", txt, {"format": "ndjson"})]
        try:
            obj = json.loads(txt)
        except Exception:
            return [make_row(path, "json", "file", "body", txt, {"format": "text"})]

        lines = []
        for k, v in _flatten(obj):
            lines.append(f"{k}={v}")
        return [make_row(path, "json", "file", "body", "\n".join(lines), {"format": "json"})]
