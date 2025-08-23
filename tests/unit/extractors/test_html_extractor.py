# Copyright (c) 2025 takotime808

import pytest
from pathlib import Path

from unifile.extractors.html_extractor import HtmlExtractor

def test_html_extractor_gets_visible_text(simple_html):
    ext = HtmlExtractor()
    rows = ext.extract(Path(simple_html))
    assert len(rows) == 1
    r = rows[0]
    assert r.file_type in {"html", "htm"}
    assert "Header" in r.content
    assert "Hello" in r.content
    assert "Example (https://example.com)" in r.content
