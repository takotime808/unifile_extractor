# Copyright (c) 2025 takotime808

from __future__ import annotations

from typing import List
from pathlib import Path
from pptx import Presentation

from unifile.extractors.base import (
    # Extractor,
    make_row,
    Row,
)

class PptxExtractor:
    supported_extensions = ["pptx"]

    def extract(self, path: Path) -> List[Row]:
        prs = Presentation(str(path))
        rows: List[Row] = []
        for i, slide in enumerate(prs.slides):
            texts = []
            for shape in slide.shapes:
                try:
                    if hasattr(shape, "text") and shape.text:
                        texts.append(shape.text)
                except Exception:
                    continue
            content = "\n".join(texts).strip()
            rows.append(make_row(path, "pptx", "slide", str(i), content, {"slide_index": i}))
        return rows
