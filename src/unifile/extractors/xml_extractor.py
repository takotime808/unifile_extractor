# Copyright (c) 2025 takotime808

from __future__ import annotations

from pathlib import Path
from typing import List
from bs4 import BeautifulSoup

from unifile.extractors.base import (
    BaseExtractor,
    make_row,
    Row,
)


class XmlExtractor(BaseExtractor):
    """XML --> visible text (BeautifulSoup+lxml)."""
    supported_extensions = ["xml"]

    def _extract(self, path: Path) -> List[Row]:
        xml = path.read_text(errors="replace")
        soup = BeautifulSoup(xml, "lxml-xml")
        text = soup.get_text("\n")
        root = soup.find()  # first tag
        root_name = root.name if root else None
        return [make_row(path, "xml", "file", "body", text, {"root": root_name})]
