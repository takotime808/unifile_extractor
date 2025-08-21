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


class HtmlExtractor(BaseExtractor):
    """
    HTML --> plain-text extractor.

    This extractor parses an HTML/HTM file and emits a single standardized
    row containing the document's visible text. `<br>` elements are converted
    to newlines prior to text extraction.

    It inherits :meth:`BaseExtractor.extract` for path validation and
    exception-to-error-row wrapping. The parsing logic is implemented in
    :meth:`_extract`.

    Output Row
    ----------
    - file_type: "html" or "htm" (normalized from the file suffix)
    - unit_type: "file"
    - unit_id:   "body"
    - content:   Visible text with newlines preserved
    - metadata:  {"title": <str | None>}
    """

    supported_extensions = ["html", "htm"]

    def _extract(self, path: Path) -> List[Row]:
        """
        Parse an HTML file into a single standardized text row.

        Parameters
        ----------
        path
            Path to an `.html`/`.htm` file. Existence checks are handled by
            :class:`BaseExtractor.extract`.

        Returns
        -------
        list[Row]
            A single row with visible text content and optional page title.
        """
        html = path.read_text(errors="replace")
        soup = BeautifulSoup(html, "lxml")

        # Convert <br> tags into newlines to preserve intended line breaks
        for br in soup.find_all("br"):
            br.replace_with("\n")

        # Extract visible text; BeautifulSoup collapses whitespace appropriately
        text = soup.get_text("\n")

        file_type = path.suffix.lstrip(".").lower() or "html"
        title = soup.title.string if soup.title else None

        return [
            make_row(
                path=path,
                file_type=file_type,
                unit_type="file",
                unit_id="body",
                content=text,
                metadata={"title": title},
                status="ok",
            )
        ]
