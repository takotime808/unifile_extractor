# Copyright (c) 2025 takotime808

from __future__ import annotations

import os
import io
from typing import List
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import os
import random

from unifile.extractors.base import (
    BaseExtractor,
    make_row,
    Row,
)


class PdfExtractor(BaseExtractor):
    """
    PDF --> text extractor with optional OCR fallback.

    For each page:
      1. Attempt native text extraction via PyMuPDF (`page.get_text("text")`).
      2. If the result is empty **and** OCR is enabled, rasterize the page and
         perform OCR with Tesseract (`pytesseract`).

    A final, optional **document-level metadata** row is appended with
    `unit_type="file"` and `unit_id="meta"`.

    Environment overrides
    ---------------------
    - `UNIFILE_DISABLE_PDF_OCR` (truthy -> disables OCR fallback)
    - `UNIFILE_OCR_LANG` (e.g., "eng", "deu", "spa")

    Output Rows
    -----------
    * Per page (index `i`):
        - file_type: "pdf"
        - unit_type: "page"
        - unit_id:   str(i)
        - content:   extracted text (native or OCR)
        - metadata:  {"page": i, "rect": [x0,y0,x1,y1], "ocr": bool}
    * Document metadata (optional):
        - file_type: "pdf"
        - unit_type: "file"
        - unit_id:   "meta"
        - metadata:  {"metadata": <dict from PyMuPDF>}

    Notes
    -----
    - On OCR errors for a specific page, an **error row** is emitted for that
      page with `status="error"` and a `"warning": "OCR failed"` metadata tag;
      processing continues for subsequent pages.
    - Path validation and exception wrapping for unexpected top-level failures
      are provided by :class:`BaseExtractor.extract`.
    """

    supported_extensions = ["pdf"]

    def __init__(self, ocr_if_empty: bool = True, ocr_langs: str = "eng", deterministic: bool = False):
        """Create a new :class:`PdfExtractor`.

        Parameters
        ----------
        ocr_if_empty:
            If True, OCR is attempted when a page yields no native text.
        ocr_langs:
            One or more Tesseract language codes joined by ``+`` (e.g.,
            ``"eng+spa"``). The order acts as a fallback preference.
        deterministic:
            When ``True`` a fixed OCR profile is used: DPI, seeds and language
            order are stabilised for reproducible tests.
        """
        self.ocr_if_empty = ocr_if_empty
        self.ocr_langs = ocr_langs
        self.deterministic = deterministic

    def _extract(self, path: Path) -> List[Row]:
        """
        Extract text from a PDF file, with optional OCR fallback.

        Parameters
        ----------
        path
            Path to a `.pdf` file. Existence checks are handled by
            :class:`BaseExtractor.extract`.

        Returns
        -------
        list[Row]
            Page rows (and a metadata row if available).
        """
        # Allow CLI / env overrides
        env_disable = os.getenv("UNIFILE_DISABLE_PDF_OCR")
        env_langs = os.getenv("UNIFILE_OCR_LANGS")
        if env_disable is not None and env_disable.strip():
            self.ocr_if_empty = False
        if env_langs:
            self.ocr_langs = env_langs
        if os.getenv("UNIFILE_DETERMINISTIC"):
            self.deterministic = True
        if self.deterministic:
            random.seed(0)

        rows: List[Row] = []

        # Use context manager to ensure the document is closed
        with fitz.open(str(path)) as doc:
            for i, page in enumerate(doc):
                text = page.get_text("text") or ""
                meta = {"page": i, "rect": list(page.rect), "ocr": False}

                if (not text.strip()) and self.ocr_if_empty:
                    try:
                        # High-res rasterization for better OCR quality
                        mat = fitz.Matrix(2.0, 2.0)
                        pix = page.get_pixmap(matrix=mat)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        config = "--dpi 300" if self.deterministic else ""
                        text = (
                            pytesseract.image_to_string(
                                img, lang=self.ocr_langs, config=config
                            )
                            or ""
                        )
                        meta["ocr"] = True
                    except Exception as e:
                        # Emit an error row for this page but continue with others
                        rows.append(
                            make_row(
                                path,
                                "pdf",
                                "page",
                                str(i),
                                text,
                                {**meta, "warning": "OCR failed"},
                                status="error",
                                error=str(e),
                            )
                        )
                        continue

                rows.append(
                    make_row(
                        path,
                        "pdf",
                        "page",
                        str(i),
                        text,
                        meta,
                        status="ok",
                    )
                )

            # Append document-level metadata if available
            try:
                meta = doc.metadata or {}
                rows.append(
                    make_row(
                        path,
                        "pdf",
                        "file",
                        "meta",
                        "",
                        {"metadata": meta},
                        status="ok",
                    )
                )
            except Exception:
                # Metadata can occasionally fail to read; ignore silently
                pass

        return rows
