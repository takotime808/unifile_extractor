# Copyright (c) 2025 takotime808
"""
Unified extraction pipeline.

This module wires file extensions to concrete extractor implementations and exposes
two key utilities:

- ``detect_extractor(path)``: resolve the normalized extension and return it only
  if it's supported by the registry.
- ``extract_to_table(...)``: run the appropriate extractor and return a
  standardized pandas DataFrame. The schema is:

    [source_path, source_name, file_type, unit_type, unit_id,
     content, char_count, metadata, status, error]

Design notes
-----------

* The registry maps normalized lower-case extensions (without dots) to callables
  that return **new extractor instances** (for class-based extractors). For
  function-based extractors (HTML/TXT/MD here), the pipeline calls them directly.
* ``extract_to_table`` accepts either a filesystem path or raw bytes plus a
  filename hint; in the latter case data is persisted to a temporary file so we
  can reuse file-based extractors uniformly.

CLI-related runtime options
--------------------------
The pipeline can accept the same flags the CLI exposes:

Quality & layout
  * ``enable_tables`` (bool): allow extractors to emit table rows/metadata
  * ``enable_block_types`` (bool): allow block typing annotations
  * ``metadata_mode`` (str): "basic" or "full" metadata

OCR / PDF
  * ``ocr_lang`` (str): language code for OCR (images and PDF OCR fallback)
  * ``no_ocr`` (bool): disable OCR fallback for PDFs (vector text only)

ASR / Media (optional, if media extractors installed)
  * ``asr_backend`` (str): "auto","dummy","whisper","faster-whisper","whispercpp"
  * ``asr_model`` (str): ASR model name (e.g., "small")
  * ``asr_device`` (str): "cpu" or "cuda"
  * ``asr_compute_type`` (str): faster-whisper compute type (e.g., "float16")
  * ``media_chunk_seconds`` (int): target segment length for streaming ASR

These are set via ``extract_to_table(..., enable_tables=..., enable_block_types=..., metadata_mode=..., ocr_*=..., asr_*=...)``
and also exported to environment variables so optional extractors can pick them up:

- UNIFILE_ENABLE_TABLES
- UNIFILE_ENABLE_BLOCK_TYPES
- UNIFILE_METADATA_MODE
- UNIFILE_OCR_LANG
- UNIFILE_DISABLE_PDF_OCR
- UNIFILE_ASR_BACKEND
- UNIFILE_ASR_MODEL
- UNIFILE_ASR_DEVICE
- UNIFILE_ASR_COMPUTE_TYPE
- UNIFILE_MEDIA_CHUNK_SECONDS
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Union, Any, Dict
import pandas as pd

from unifile.utils.utils import write_temp_file, norm_ext
from unifile.extractors.base import Row
from unifile.extractors.pdf_extractor import PdfExtractor
from unifile.extractors.docx_extractor import DocxExtractor
from unifile.extractors.pptx_extractor import PptxExtractor
from unifile.extractors.img_extractor import ImageExtractor
# NOTE: function-based extractors for HTML/TEXT:
from unifile.extractors.html_extractor import extract_html
from unifile.extractors.text_extractor import extract_textlike
from unifile.extractors.xlsx_extractor import ExcelExtractor, CsvExtractor
from unifile.extractors.eml_extractor import EmlExtractor

# Optional extractors (installed via extras)
try:
    # Install with: pip install .[archive]
    from unifile.extractors.archive_extractor import ArchiveExtractor
    from unifile.extractors.epub_extractor import EpubExtractor
    from unifile.extractors.json_extractor import JsonExtractor
    from unifile.extractors.xml_extractor import XmlExtractor
    INCLUDE_FILE_TYPES_COMPRESSED = True
except Exception:
    INCLUDE_FILE_TYPES_COMPRESSED = False

try:
    # Install with: pip install .[media]
    from unifile.extractors.audio_extractor import AudioExtractor
    from unifile.extractors.video_extractor import VideoExtractor
    INCLUDE_FILE_TYPES_MEDIA = True
except Exception:
    INCLUDE_FILE_TYPES_MEDIA = False


# ------------------------- Runtime configuration layer -------------------------

# Defaults used unless overridden via extract_to_table kwargs
_RUNTIME = {
    # Quality / layout
    "enable_tables": True,
    "enable_block_types": True,
    "metadata_mode": "basic",  # or "full"

    # OCR / PDF
    "ocr_lang": "eng",
    "disable_pdf_ocr": False,  # True when CLI --no-ocr is passed

    # Media ASR
    "asr_backend": "auto",
    "asr_model": None,
    "asr_device": None,
    "asr_compute_type": None,
    "media_chunk_seconds": 30,
}

def _apply_runtime_env():
    """
    Export the current runtime configuration into environment variables so that
    extractors that read env (e.g., PdfExtractor, audio/video ASR backends) see
    consistent settings.
    """
    # Quality
    os.environ["UNIFILE_ENABLE_TABLES"] = "1" if _RUNTIME["enable_tables"] else ""
    os.environ["UNIFILE_ENABLE_BLOCK_TYPES"] = "1" if _RUNTIME["enable_block_types"] else ""
    os.environ["UNIFILE_METADATA_MODE"] = str(_RUNTIME["metadata_mode"] or "basic")

    # OCR
    os.environ["UNIFILE_OCR_LANG"] = _RUNTIME["ocr_lang"] or "eng"
    os.environ["UNIFILE_DISABLE_PDF_OCR"] = "1" if _RUNTIME["disable_pdf_ocr"] else ""

    # ASR / media
    os.environ["UNIFILE_ASR_BACKEND"] = str(_RUNTIME["asr_backend"] or "auto")
    if _RUNTIME["asr_model"] is not None:
        os.environ["UNIFILE_ASR_MODEL"] = str(_RUNTIME["asr_model"])
    if _RUNTIME["asr_device"] is not None:
        os.environ["UNIFILE_ASR_DEVICE"] = str(_RUNTIME["asr_device"])
    if _RUNTIME["asr_compute_type"] is not None:
        os.environ["UNIFILE_ASR_COMPUTE_TYPE"] = str(_RUNTIME["asr_compute_type"])
    os.environ["UNIFILE_MEDIA_CHUNK_SECONDS"] = str(int(_RUNTIME["media_chunk_seconds"]))


def set_runtime_options(
    *,
    # quality
    enable_tables: Optional[bool] = None,
    enable_block_types: Optional[bool] = None,
    metadata_mode: Optional[str] = None,
    # OCR
    ocr_lang: Optional[str] = None,
    no_ocr: Optional[bool] = None,
    # ASR
    asr_backend: Optional[str] = None,
    asr_model: Optional[str] = None,
    asr_device: Optional[str] = None,
    asr_compute_type: Optional[str] = None,
    media_chunk_seconds: Optional[int] = None,
) -> None:
    """
    Update in-process runtime options (mirrors CLI flags) and export to env.
    """
    if enable_tables is not None:
        _RUNTIME["enable_tables"] = bool(enable_tables)
    if enable_block_types is not None:
        _RUNTIME["enable_block_types"] = bool(enable_block_types)
    if metadata_mode is not None:
        _RUNTIME["metadata_mode"] = str(metadata_mode)

    if ocr_lang is not None:
        _RUNTIME["ocr_lang"] = ocr_lang
    if no_ocr is not None:
        _RUNTIME["disable_pdf_ocr"] = bool(no_ocr)

    if asr_backend is not None:
        _RUNTIME["asr_backend"] = asr_backend
    if asr_model is not None:
        _RUNTIME["asr_model"] = asr_model
    if asr_device is not None:
        _RUNTIME["asr_device"] = asr_device
    if asr_compute_type is not None:
        _RUNTIME["asr_compute_type"] = asr_compute_type
    if media_chunk_seconds is not None:
        _RUNTIME["media_chunk_seconds"] = int(media_chunk_seconds)

    _apply_runtime_env()


# ----------------------------- Registry & factories -----------------------------

# Base registry for *class-based* extractors only.
# (HTML/TEXT are handled functionally below.)
REGISTRY_BASE = {
    "pdf": lambda: PdfExtractor(),
    "docx": lambda: DocxExtractor(),
    "pptx": lambda: PptxExtractor(),
    # spreadsheets
    "xlsx": lambda: ExcelExtractor(),
    "xls": lambda: ExcelExtractor(),
    "xlsm": lambda: ExcelExtractor(),
    "xltx": lambda: ExcelExtractor(),
    "xltm": lambda: ExcelExtractor(),
    "csv": lambda: CsvExtractor(),
    "tsv": lambda: CsvExtractor(),
    # images (OCR)
    "png": lambda: ImageExtractor(),
    "jpg": lambda: ImageExtractor(),
    "jpeg": lambda: ImageExtractor(),
    "bmp": lambda: ImageExtractor(),
    "tif": lambda: ImageExtractor(),
    "tiff": lambda: ImageExtractor(),
    "webp": lambda: ImageExtractor(),
    "gif": lambda: ImageExtractor(),
    # eml
    "eml":  lambda: EmlExtractor(),
}

if INCLUDE_FILE_TYPES_COMPRESSED:
    REGISTRY_BASE.update({
        # compressed / containers
        "zip":  lambda: ArchiveExtractor(),
        "tar":  lambda: ArchiveExtractor(),
        "gz":   lambda: ArchiveExtractor(),
        "tgz":  lambda: ArchiveExtractor(),
        "bz2":  lambda: ArchiveExtractor(),
        "tbz":  lambda: ArchiveExtractor(),
        "xz":   lambda: ArchiveExtractor(),
        # epub
        "epub": lambda: EpubExtractor(),
        # json
        "json": lambda: JsonExtractor(),
        # xml
        "xml":  lambda: XmlExtractor(),
    })

if INCLUDE_FILE_TYPES_MEDIA:
    REGISTRY_BASE.update({
        # audio
        "wav":  lambda: AudioExtractor(),
        "mp3":  lambda: AudioExtractor(),
        "m4a":  lambda: AudioExtractor(),
        "flac": lambda: AudioExtractor(),
        "ogg":  lambda: AudioExtractor(),
        "webm": lambda: AudioExtractor(),  # audio-only webm treated as audio here
        "aac":  lambda: AudioExtractor(),
        # video
        "mp4":  lambda: VideoExtractor(),
        "mov":  lambda: VideoExtractor(),
        "mkv":  lambda: VideoExtractor(),
    })

# Supported extensions (include function-based HTML/TEXT too)
SUPPORTED_EXTENSIONS = sorted({
    # function-based
    "html","htm","txt","md","rtf","log",
    # class-based
    *REGISTRY_BASE.keys(),
})

# Public registry (class-based). Users/tests may monkeypatch this.
REGISTRY = REGISTRY_BASE.copy()


# --------------------------------- Core API -----------------------------------

def detect_extractor(path: Union[str, Path]) -> Optional[str]:
    """
    Determine the extractor to use from a path-like object's extension.
    """
    ext = norm_ext(path)
    return ext if ext in SUPPORTED_EXTENSIONS else None


def _rows_to_df(rows: List[Union[Row, Dict[str, Any]]]) -> pd.DataFrame:
    """
    Convert a list of Row (class-based) OR row dicts (function-based) to the standardized DataFrame.
    """
    data: List[Dict[str, Any]] = []
    for r in rows:
        if isinstance(r, Row):
            data.append(r.to_dict())
        else:
            data.append(dict(r))
    cols = [
        "source_path", "source_name", "file_type", "unit_type", "unit_id",
        "content", "char_count", "metadata", "status", "error"
    ]
    df = pd.DataFrame(data)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]


def _apply_runtime_to_instance(extractor) -> None:
    """
    Best-effort: mutate known extractor attributes after construction so tests
    can monkeypatch REGISTRY and still have runtime options honored.
    """
    # Quality toggles (extractors that support them may read env variables;
    # we also set attributes when present)
    for attr, val in (("enable_tables", _RUNTIME["enable_tables"]),
                      ("enable_block_types", _RUNTIME["enable_block_types"]),
                      ("metadata_mode", _RUNTIME["metadata_mode"])):
        if hasattr(extractor, attr):
            try:
                setattr(extractor, attr, val)
            except Exception:
                pass

    # Image OCR language
    if isinstance(extractor, ImageExtractor):
        try:
            extractor.ocr_lang = _RUNTIME["ocr_lang"] or extractor.ocr_lang
        except Exception:
            pass
    # PDF OCR flags
    if isinstance(extractor, PdfExtractor):
        try:
            extractor.ocr_lang = _RUNTIME["ocr_lang"] or extractor.ocr_lang
            extractor.ocr_if_empty = not _RUNTIME["disable_pdf_ocr"]
        except Exception:
            pass
    # Media (if present)
    if INCLUDE_FILE_TYPES_MEDIA and (
        isinstance(extractor, globals().get("AudioExtractor", object)) or
        isinstance(extractor, globals().get("VideoExtractor", object))
    ):
        for attr, val in (("asr_backend", _RUNTIME["asr_backend"]),
                          ("asr_model", _RUNTIME["asr_model"]),
                          ("asr_device", _RUNTIME["asr_device"]),
                          ("asr_compute_type", _RUNTIME["asr_compute_type"]),
                          ("chunk_seconds", _RUNTIME["media_chunk_seconds"])):
            if val is not None and hasattr(extractor, attr):
                try:
                    setattr(extractor, attr, val)
                except Exception:
                    pass


def _run_html_or_text(ext: str, path: Path) -> List[Dict[str, Any]]:
    """
    Call the function-based extractors for HTML/TEXT with the current runtime knobs.
    """
    if ext in {"html", "htm"}:
        return extract_html(str(path),
                            enable_tables=_RUNTIME["enable_tables"],
                            enable_block_types=_RUNTIME["enable_block_types"])
    # txt-like
    return extract_textlike(str(path),
                            enable_block_types=_RUNTIME["enable_block_types"])


def extract_to_table(
    input_obj: Union[str, Path, bytes],
    *,
    filename: Optional[str] = None,
    # quality
    enable_tables: Optional[bool] = None,
    enable_block_types: Optional[bool] = None,
    metadata_mode: Optional[str] = None,
    # OCR
    ocr_lang: Optional[str] = None,
    no_ocr: Optional[bool] = None,
    # ASR
    asr_backend: Optional[str] = None,
    asr_model: Optional[str] = None,
    asr_device: Optional[str] = None,
    asr_compute_type: Optional[str] = None,
    media_chunk_seconds: Optional[int] = None,
) -> pd.DataFrame:
    """
    Extract text from a supported file and return a standardized pandas DataFrame.
    Works with both class-based extractors (most formats) and the new function-based
    HTML/TEXT extractors.
    """
    # Update runtime config (and environment) from provided options
    set_runtime_options(
        enable_tables=enable_tables,
        enable_block_types=enable_block_types,
        metadata_mode=metadata_mode,
        ocr_lang=ocr_lang,
        no_ocr=no_ocr,
        asr_backend=asr_backend,
        asr_model=asr_model,
        asr_device=asr_device,
        asr_compute_type=asr_compute_type,
        media_chunk_seconds=media_chunk_seconds,
    )

    # Resolve to a real file path
    if isinstance(input_obj, (str, Path)):
        path = Path(input_obj)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Not a file: {path}")
    else:
        if not filename:
            raise ValueError("filename is required when input_obj is bytes to detect extension")
        path = write_temp_file(input_obj, suffix=Path(filename).suffix or ".bin")

    ext = detect_extractor(path)
    if not ext:
        raise ValueError(
            f"Unsupported file extension '{path.suffix}'. "
            f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    # Function-based extractors (HTML/TEXT family)
    if ext in {"html","htm","txt","md","rtf","log"}:
        rows = _run_html_or_text(ext, path)
        return _rows_to_df(rows)

    # Class-based extractors (existing)
    factory = REGISTRY[ext]
    extractor = factory()
    _apply_runtime_to_instance(extractor)
    rows = extractor.extract(path)
    return _rows_to_df(rows)
