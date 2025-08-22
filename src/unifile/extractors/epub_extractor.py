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
    """Extractor for EPUB files using ebooklib and BeautifulSoup.

    This extractor parses EPUB books, extracts text from each chapter
    (document item), and emits one row per chapter. If no chapters are
    found, a single row is returned with a warning in the metadata.
    """
    supported_extensions = ["epub"]

    def _extract(self, path: Path) -> List[Row]:
        """Extract chapter text from an EPUB file.

        The extractor reads the EPUB container, iterates through its
        document items (chapters), and collects their visible text content
        using BeautifulSoup. Each chapter is represented as a separate row.

        Args:
            path (Path): Path to the EPUB file.

        Returns:
            List[Row]: A list of rows with:
                - source type: ``epub``
                - level: ``chapter`` (or ``file`` if no chapters found)
                - section: Chapter index (as string) or ``"body"``
                - text: Extracted visible text content
                - metadata: Dictionary with:
                    - ``"id"``: The EPUB item ID (per chapter)
                    - ``"warning"``: Present if no chapters were found
        """
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
