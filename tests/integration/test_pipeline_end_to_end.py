# Copyright (c) 2025 takotime808

# import os
# from pathlib import Path
# import pandas as pd
import pytest

# Try to import from a src-layout or installed package
try:
    from unifile.pipeline import extract_to_table, detect_extractor
except Exception as e:
    pytest.skip("unifile.pipeline not importable in this environment", allow_module_level=True)

from .utils_build_samples import (
    build_txt, build_html, build_docx, build_pptx, build_xlsx, build_csv, build_image_png, build_pdf
)

import unifile.extractors.img_extractor as mod
from unifile.pipeline import extract_to_table

EXPECTED_COLS = ["source_path","source_name","file_type","unit_type","unit_id","content","char_count","metadata","status","error"]

@pytest.mark.parametrize("builder,ext", [
    (build_txt, "txt"),
    (build_html, "html"),
    (build_docx, "docx"),
    (build_pptx, "pptx"),
    (build_xlsx, "xlsx"),
    (build_csv, "csv"),
    (build_image_png, "png"),
    (build_pdf, "pdf"),
])
def test_extract_to_table_all_types(tmp_path, builder, ext, monkeypatch):
    # For image OCR, avoid Tesseract dependency by mocking pytesseract
    if ext in ("png","jpg","jpeg","tiff","bmp","webp"):
        monkeypatch.setattr(mod, "pytesseract", type("X", (), {"image_to_string": staticmethod(lambda img, lang='eng': "HELLO MOCK")}))
    f = tmp_path / f"sample.{ext}"
    builder(f)
    assert detect_extractor(f) == ext
    df = extract_to_table(f)

    # schema
    assert list(df.columns) == EXPECTED_COLS
    # at least one row and content is string
    assert len(df) >= 1
    assert df["content"].map(lambda x: isinstance(x, str)).all()
    # metadata is a dict for all rows
    assert df["metadata"].map(lambda x: isinstance(x, dict)).all()

def test_bytes_input(tmp_path):
    # build a small TXT and feed bytes + filename
    f = tmp_path / "a.txt"
    f.write_text("bytes route")
    df = extract_to_table(f.read_bytes(), filename="a.txt")
    assert "bytes route" in df["content"].iloc[0]
