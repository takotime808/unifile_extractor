# Copyright (c) 2025 takotime808

import pytest
from pathlib import Path
from unifile.extractors.txt_extractor import TextExtractor

def test_text_extractor_reads_text(simple_txt):
    ext = TextExtractor()
    rows = ext.extract(Path(simple_txt))
    assert len(rows) == 1
    r = rows[0]
    assert r.file_type in {"txt", "md", "rtf", "log"}
    assert r.unit_type == "file"
    assert r.unit_id == "body"
    assert "hello" in r.content and "world" in r.content
    assert r.char_count == len(r.content)
