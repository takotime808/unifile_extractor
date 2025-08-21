# Copyright (c) 2025 takotime808

from __future__ import annotations

from pathlib import Path
from typing import List
from bs4 import BeautifulSoup
from ebooklib import epub

from unifile.extractors.base import (
    BaseExtractor,
    make_row,
    Row,
)


class EpubExtractor(BaseExtractor):
    """EPUB --> concatenated chapter text; emits one row per item (chapter)."""
    supported_extensions = ["epub"]

    def _extract(self, path: Path) -> List[Row]:
        book = epub.read_epub(str(path))
        rows: List[Row] = []
        for i, item in enumerate(book.get_items_of_type(9)):  # 9: DOCUMENT
            html = item.get_content().decode("utf-8", errors="replace")
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text("\n")
            rows.append(make_row(path, "epub", "chapter", str(i), text, {"id": item.get_id()}))
        if not rows:
            rows.append(make_row(path, "epub", "file", "body", "", {"warning": "no chapters found"}))
        return rows
