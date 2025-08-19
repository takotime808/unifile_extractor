# Copyright (c) 2025 takotime808

from __future__ import annotations

from pathlib import Path
from typing import List
from PIL import Image
import pytesseract

from unifile.extractors.base import (
    # Extractor,
    make_row,
    Row,
)

class ImageExtractor:
    supported_extensions = ["png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp", "gif"]

    def __init__(self, ocr_lang: str = "eng"):
        self.ocr_lang = ocr_lang

    def extract(self, path: Path) -> List[Row]:
        img = Image.open(str(path))
        if img.mode in ("P", "RGBA"):
            img = img.convert("RGB")
        text = pytesseract.image_to_string(img, lang=self.ocr_lang) or ""
        meta = {"width": img.width, "height": img.height, "mode": img.mode}
        return [make_row(path, path.suffix.lstrip('.').lower(), "image", "0", text, meta)]
