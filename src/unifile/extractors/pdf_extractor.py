# Copyright (c) 2025 takotime808

from __future__ import annotations

import os
import io
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from typing import List
from pathlib import Path

from unifile.extractors.base import (
    # Extractor, 
    make_row, 
    Row,
)

class PdfExtractor:
    supported_extensions = ["pdf"]

    def __init__(self, ocr_if_empty: bool = True, ocr_lang: str = "eng"):
        self.ocr_if_empty = ocr_if_empty
        self.ocr_lang = ocr_lang

    def extract(self, path: Path) -> List[Row]:
        # Allow CLI to override via environment variables
        env_disable = os.getenv("UNIFILE_DISABLE_PDF_OCR")
        env_lang = os.getenv("UNIFILE_OCR_LANG")
        if env_disable is not None and env_disable.strip():
            self.ocr_if_empty = False
        if env_lang:
            self.ocr_lang = env_lang

        rows: List[Row] = []
        doc = fitz.open(str(path))
        for i, page in enumerate(doc):
            text = page.get_text("text") or ""
            meta = {"page": i, "rect": list(page.rect), "ocr": False}
            if (not text.strip()) and self.ocr_if_empty:
                try:
                    # High-res rasterization for OCR
                    mat = fitz.Matrix(2.0, 2.0)
                    pix = page.get_pixmap(matrix=mat)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    text = pytesseract.image_to_string(img, lang=self.ocr_lang) or ""
                    meta["ocr"] = True
                except Exception as e:
                    rows.append(make_row(path, "pdf", "page", str(i), text,
                                         {**meta, "warning": "OCR failed"},
                                         status="error", error=str(e)))
                    continue
            rows.append(make_row(path, "pdf", "page", str(i), text, meta, status="ok"))
        # add doc-level metadata row
        try:
            meta = doc.metadata or {}
            rows.append(make_row(path, "pdf", "file", "meta", "", {"metadata": meta}, status="ok"))
        except Exception:
            pass
        doc.close()
        return rows
