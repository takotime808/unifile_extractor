# Copyright (c) 2025 takotime808
import pytest
from pathlib import Path

import unifile.pipeline as pipeline
from unifile.extractors.base import make_row

class StubPdf:
    def __init__(self, ocr_if_empty=True, ocr_lang="eng"):
        self.args = (ocr_if_empty, ocr_lang)
    def extract(self, path: Path):
        return [make_row(path, "pdf", "page", "0", "X", {"args": self.args})]

def test_defaults_when_no_options_provided(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "PdfExtractor", StubPdf)
    f = tmp_path / "d.pdf"; f.write_bytes(b"%PDF")
    df = pipeline.extract_to_table(f)
    args = df.iloc[0]["metadata"]["args"]
    # default runtime from pipeline should be (not disabled, 'eng')
    assert args == (True, "eng")
