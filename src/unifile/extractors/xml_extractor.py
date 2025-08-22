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
    """Extractor for XML files using BeautifulSoup with the lxml-xml parser.

    This extractor reads XML files, parses them with BeautifulSoup,
    and extracts the visible text content. The root tag name of the
    document is also included in the extracted metadata.
    """
    supported_extensions = ["xml"]

    def _extract(self, path: Path) -> List[Row]:
        """Extract text content from an XML file.

        The method reads the XML file, parses it with the ``lxml-xml`` parser,
        and returns a single row containing all visible text. The row metadata
        includes the name of the root tag, if present.

        Args:
            path (Path): Path to the XML file.

        Returns:
            List[Row]: A list containing one row with:
                - source type: ``xml``
                - level: ``file``
                - section: ``body``
                - text: Extracted visible text content
                - metadata: Dictionary with the root tag name under ``"root"``
        """
        xml = path.read_text(errors="replace")
        soup = BeautifulSoup(xml, "lxml-xml")
        text = soup.get_text("\n")
        root = soup.find()  # first tag
        root_name = root.name if root else None
        return [make_row(path, "xml", "file", "body", text, {"root": root_name})]
