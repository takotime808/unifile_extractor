# Copyright (c) 2025 takotime808

from __future__ import annotations

from pathlib import Path
from typing import List
from docx import Document

from unifile.extractors.base import (
    # Extractor,
    make_row,
    Row,
)

class DocxExtractor:
    supported_extensions = ["docx"]

    def extract(self, path: Path) -> List[Row]:
        doc = Document(str(path))
        texts = []
        # paragraphs
        for p in doc.paragraphs:
            if p.text:
                texts.append(p.text)
        # tables
        table_blobs = []
        for ti, t in enumerate(doc.tables):
            blob = []
            for row in t.rows:
                blob.append("\t".join(cell.text or "" for cell in row.cells))
            table_text = "\n".join(blob).strip()
            if table_text:
                table_blobs.append((ti, table_text))
        rows: List[Row] = []
        if texts:
            rows.append(make_row(path, "docx", "file", "body", "\n".join(texts).strip(), {"sections": "paragraphs"}))
        for ti, blob in table_blobs:
            rows.append(make_row(path, "docx", "table", str(ti), blob, {"table_index": ti}))
        return rows
