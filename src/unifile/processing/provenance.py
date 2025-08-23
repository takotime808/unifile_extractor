"""Utilities for extracting text with provenance information.

This module exposes :func:`extract_provenance` which returns low-level text
spans alongside their location within the source document. It currently
supports **PDF**, **image** and **HTML** files.  For PDFs the bounding boxes are
reported using coordinates from PyMuPDF.  Image provenance relies on
``pytesseract.image_to_data`` to provide bounding boxes for OCR'd text.  HTML
files do not expose layout information so ``bbox`` is always ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union, TypedDict

import fitz  # PyMuPDF
from bs4 import BeautifulSoup
from PIL import Image
import pytesseract


@dataclass
class Provenance:
    """A single text span with location information."""

    text: str
    page: int
    bbox: Optional[List[float]]
    block_id: str
    source_path: str


class ProvenanceDict(TypedDict):
    """Typed dictionary version of :class:`Provenance`."""

    text: str
    page: int
    bbox: Optional[List[float]]
    block_id: str
    source_path: str


_SUPPORTED_IMAGE_EXTS = {
    "png",
    "jpg",
    "jpeg",
    "bmp",
    "tif",
    "tiff",
    "webp",
    "gif",
    "heic",
    "heif",
}


def extract_provenance(path: Union[str, Path]) -> List[Provenance]:
    """Extract text spans with provenance information.

    Parameters
    ----------
    path:
        File to process.  PDFs, images and HTML files are supported.

    Returns
    -------
    list[Provenance]
        Each item exposes ``text``, ``page``, ``bbox``, ``block_id`` and
        ``source_path`` fields.
    """
    p = Path(path)
    ext = p.suffix.lower().lstrip(".")

    if ext == "pdf":
        out: List[Provenance] = []
        with fitz.open(str(p)) as doc:
            for page_num, page in enumerate(doc):
                for bid, block in enumerate(page.get_text("blocks")):
                    x0, y0, x1, y1, text, *_ = block
                    out.append(
                        Provenance(
                            text=(text or "").strip(),
                            page=page_num,
                            bbox=[x0, y0, x1, y1],
                            block_id=str(bid),
                            source_path=str(p),
                        )
                    )
        return out

    if ext in _SUPPORTED_IMAGE_EXTS:
        with Image.open(str(p)) as img:
            data = pytesseract.image_to_data(
                img, lang="eng", output_type=pytesseract.Output.DICT
            )
        out: List[Provenance] = []
        for i, txt in enumerate(data.get("text", [])):
            if not txt or not txt.strip():
                continue
            x = data["left"][i]
            y = data["top"][i]
            w = data["width"][i]
            h = data["height"][i]
            out.append(
                Provenance(
                    text=txt,
                    page=0,
                    bbox=[x, y, x + w, y + h],
                    block_id=str(i),
                    source_path=str(p),
                )
            )
        return out

    if ext in {"html", "htm"}:
        html = p.read_text(errors="replace")
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        out: List[Provenance] = []
        for i, text in enumerate(soup.stripped_strings):
            out.append(
                Provenance(
                    text=text,
                    page=0,
                    bbox=None,
                    block_id=str(i),
                    source_path=str(p),
                )
            )
        return out

    raise ValueError(f"Unsupported file type for provenance extraction: {p.suffix}")
