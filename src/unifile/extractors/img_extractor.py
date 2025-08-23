# Copyright (c) 2025 takotime808

from __future__ import annotations

from pathlib import Path
from typing import List
from PIL import Image
import pytesseract
import os
import random

try:  # pragma: no cover - optional dependency
    from pillow_heif import register_heif_opener

    register_heif_opener()
    _HAS_HEIF = True
except Exception:  # pragma: no cover - graceful degradation
    _HAS_HEIF = False

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
    png, jpg, jpeg, tif, tiff, bmp, webp, gif, heic, heif

    Output Row
    ----------
    - file_type: normalized from the file suffix (e.g., "png")
    - unit_type: "image"
    - unit_id:   "0"
    - content:   OCR text (empty string if none)
    - metadata:  {"width": int, "height": int, "mode": str}
    """

    supported_extensions = [
        "png",
        "jpg",
        "jpeg",
        "tif",
        "tiff",
        "bmp",
        "webp",
        "gif",
    ]
    if _HAS_HEIF:
        supported_extensions.extend(["heic", "heif"])

    def __init__(self, ocr_langs: str = "eng", deterministic: bool = False):
        """Create a new :class:`ImageExtractor`.

        Parameters
        ----------
        ocr_langs:
            One or more Tesseract language codes joined by ``+`` (e.g.,
            ``"eng+spa"``). The order acts as a fallback preference.
        deterministic:
            When ``True`` a fixed OCR profile is used: DPI, seeds and language
            order are stabilised for reproducible tests.
        """
        self.ocr_langs = ocr_langs
        self.deterministic = deterministic

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
        env_langs = os.getenv("UNIFILE_OCR_LANGS")
        if env_langs:
            self.ocr_langs = env_langs
        if os.getenv("UNIFILE_DETERMINISTIC"):
            self.deterministic = True

        if self.deterministic:
            random.seed(0)

        config = "--dpi 300" if self.deterministic else ""

        # Open via context manager to ensure resources are freed.
        with Image.open(str(path)) as img:
            # Normalize palette/alpha images to RGB for better OCR behavior.
            if img.mode in ("P", "RGBA"):
                img = img.convert("RGB")

            text = (
                pytesseract.image_to_string(
                    img, lang=self.ocr_langs, config=config
                )
                or ""
            )
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
