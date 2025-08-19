# Copyright (c) 2025 takotime808

import os
import pytest
import fitz  # PyMuPDF
from pathlib import Path

from unifile.extractors.pdf_extractor import PdfExtractor

def _build_pdf(path: Path):

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello PDF Page 1")
    doc.save(str(path))
    doc.close()

def test_pdf_extractor_vector_text(tmp_path, monkeypatch):
    p = tmp_path / "sample.pdf"
    _build_pdf(p)

    # Ensure OCR fallback is disabled via env to test the vector text path deterministically
    monkeypatch.setenv("UNIFILE_DISABLE_PDF_OCR", "1")
    ext = PdfExtractor()
    rows = ext.extract(p)
    # Should have at least one page row; optionally a meta row
    page_rows = [r for r in rows if r.unit_type == "page"]
    assert page_rows and "Hello PDF Page 1" in page_rows[0].content
    # meta row is optional but if present should be unit_id == "meta"
    meta_rows = [r for r in rows if r.unit_type == "file"]
    for mr in meta_rows:
        assert mr.unit_id in {"meta"}
