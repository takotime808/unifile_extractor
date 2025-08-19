# Copyright (c) 2025 takotime808

from __future__ import annotations

from typing import List
from pathlib import Path
from unifile.extractors.base import (
    # Extractor,
    make_row,
    Row,
)

class TextExtractor:
    supported_extensions = ["txt", "md", "rtf", "log"]

    def extract(self, path: Path) -> List[Row]:
        # try to detect encoding
        try:
            import chardet # TODO: move import and test
            raw = path.read_bytes()
            enc = chardet.detect(raw).get("encoding") or "utf-8"
            text = raw.decode(enc, errors="replace")
        except Exception:
            text = path.read_text(errors="replace")
        return [make_row(path, path.suffix.lstrip('.').lower(), "file", "body", text, {"encoding": "auto"})]
