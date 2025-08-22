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
    """Recursively flatten a nested JSON object.

    Converts nested dictionaries and lists into dot/bracket-delimited
    key paths with corresponding values, suitable for text extraction.

    Args:
        obj: A JSON object (dict, list, or scalar).
        prefix (str, optional): String prefix used for recursive key building.
            Defaults to an empty string.

    Yields:
        Tuple[str, Any]: A tuple containing the flattened key path and its value.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _flatten(v, f"{prefix}{k}.")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _flatten(v, f"{prefix}{i}.")
    else:
        yield prefix[:-1], obj


class JsonExtractor(BaseExtractor):
    """Extractor for JSON and NDJSON files.

    This extractor supports:
      - **NDJSON (newline-delimited JSON)**: treated as raw text.
      - **JSON objects/arrays**: flattened into key-value pairs for easier search.

    The extracted output is returned as a single row per file with a
    ``format`` metadata field indicating the detected type.
    """
    supported_extensions = ["json"]

    def _extract(self, path: Path) -> List[Row]:
        """Extract text content from a JSON or NDJSON file.

        The extractor attempts to detect NDJSON by checking for newline-delimited
        JSON objects. If the content cannot be parsed as JSON, it is treated as
        plain text. Otherwise, nested structures are flattened into
        ``key=value`` strings, one per line.

        Args:
            path (Path): Path to the JSON file.

        Returns:
            List[Row]: A list containing one row with:
                - source type: ``json``
                - level: ``file``
                - section: ``body``
                - text: Extracted lines or raw text
                - metadata: Dictionary with a ``"format"`` key indicating
                  one of ``"ndjson"``, ``"json"``, or ``"text"``
        """
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
