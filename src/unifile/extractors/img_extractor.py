# Copyright (c) 2025 takotime808

from __future__ import annotations

from pathlib import Path
from typing import List
from PIL import Image
import pytesseract

from unifile.extractors.base import (
    BaseExtractor,
    make_row,
    Row,
)


class ImageExtractor(BaseExtractor):
    """
    Image --> text (OCR) extractor.

    This extractor opens an image, normalizes its mode for OCR, and uses
    Tesseract (via `pytesseract`) to extract text. It emits a single row with
    basic image metadata.

    Inherits :meth:`BaseExtractor.extract` for path validation and
    exception-to-error-row wrapping. The core logic lives in :meth:`_extract`.

    Supported extensions
    --------------------
    png, jpg, jpeg, tif, tiff, bmp, webp, gif

    Output Row
    ----------
    - file_type: normalized from the file suffix (e.g., "png")
    - unit_type: "image"
    - unit_id:   "0"
    - content:   OCR text (empty string if none)
    - metadata:  {"width": int, "height": int, "mode": str}
    """

    supported_extensions = ["png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp", "gif"]

    def __init__(self, ocr_lang: str = "eng"):
        """
        Parameters
        ----------
        ocr_lang
            Tesseract language code (e.g., "eng", "deu"). Must be installed in
            the system Tesseract data path to take effect.
        """
        self.ocr_lang = ocr_lang

    def _extract(self, path: Path) -> List[Row]:
        """
        Perform OCR on the image at `path` and return a single standardized row.

        Parameters
        ----------
        path
            Path to a supported image file. Existence checks are handled by
            :class:`BaseExtractor.extract`.

        Returns
        -------
        list[Row]
            A single row with OCR text and basic image metadata.
        """
        # Open via context manager to ensure resources are freed.
        with Image.open(str(path)) as img:
            # Normalize palette/alpha images to RGB for better OCR behavior.
            if img.mode in ("P", "RGBA"):
                img = img.convert("RGB")

            text = pytesseract.image_to_string(img, lang=self.ocr_lang) or ""
            meta = {"width": img.width, "height": img.height, "mode": img.mode}

        file_type = path.suffix.lstrip(".").lower() or "png"
        return [
            make_row(
                path=path,
                file_type=file_type,
                unit_type="image",
                unit_id="0",
                content=text,
                metadata=meta,
                status="ok",
            )
        ]
