# Copyright (c) 2025 takotime808

from __future__ import annotations

from pathlib import Path
from typing import List
from bs4 import BeautifulSoup

try:  # pragma: no cover - trivial import guard
    from readability import Document
except Exception:  # if readability isn't installed, fall back to raw HTML
    Document = None  # type: ignore[assignment]

from unifile.extractors.base import (
    BaseExtractor,
    make_row,
    Row,
)


class HtmlExtractor(BaseExtractor):
    """HTML → readable plain-text extractor.

    The implementation uses :mod:`readability` to isolate the main article
    content and then parses the resulting HTML with BeautifulSoup.  Hyperlinks
    are preserved in the extracted text by rendering them as ``"text (href)"``
    tokens so downstream consumers can retain link targets.

    Output Row
    ----------
    - file_type: "html" or "htm" (normalized from the file suffix)
    - unit_type: "file"
    - unit_id:   "body"
    - content:   Readability-extracted text with newlines preserved
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

        # ``readability`` is an optional dependency.  If it is available we use
        # it to isolate the primary article content and title; otherwise we just
        # operate on the raw HTML.  Any failures during readability processing
        # fall back to the unprocessed HTML as well so extraction never raises
        # during import or runtime.
        body_html = html
        title = None
        if Document is not None:  # pragma: no branch - simple feature flag
            try:
                doc = Document(html)
                body_html = doc.summary(html_partial=True)
                title = doc.short_title()
            except Exception:
                pass

        soup = BeautifulSoup(body_html, "lxml")
        for br in soup.find_all("br"):
            br.replace_with("\n")
        for a in soup.find_all("a"):
            text = a.get_text(strip=True)
            href = a.get("href", "")
            repl = f"{text} ({href})" if href else text
            a.replace_with(repl)

        text = soup.get_text("\n")
        file_type = path.suffix.lstrip(".").lower() or "html"

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
