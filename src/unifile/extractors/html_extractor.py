# Copyright (c) 2025 takotime808

from __future__ import annotations

from pathlib import Path
from typing import List
from bs4 import BeautifulSoup

from unifile.extractors.base import (
    # Extractor,
    make_row,
    Row,
)

class HtmlExtractor:
    supported_extensions = ["html", "htm"]

    def extract(self, path: Path) -> List[Row]:
        html = path.read_text(errors="replace")
        soup = BeautifulSoup(html, "lxml")
        # Convert <br> to newlines and get visible text
        for br in soup.find_all("br"):
            br.replace_with("\n")
        text = soup.get_text("\n")
        return [make_row(path, path.suffix.lstrip('.').lower(), "file", "body", text, {"title": soup.title.string if soup.title else None})]
