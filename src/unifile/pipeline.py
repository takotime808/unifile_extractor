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
  that return **new extractor instances**. This ensures extractors are stateless
  across calls.
* ``extract_to_table`` accepts either a filesystem path or raw bytes plus a
  filename hint; in the latter case data is persisted to a temporary file so we
  can reuse file-based extractors uniformly.

CLI-related runtime options
--------------------------
The pipeline can accept the same flags the CLI exposes:

- OCR / PDF
  * ``ocr_lang`` (str): legacy single language code for OCR
  * ``ocr_langs`` (str): ``+``-separated language codes for multilingual OCR
  * ``deterministic`` (bool): enforce deterministic OCR profile
  * ``no_ocr`` (bool): disable OCR fallback for PDFs (vector text only)

- ASR / Media (optional, if media extractors installed)
  * ``whisper_model`` / ``asr_model`` (str): ASR model name (e.g., "small")
  * ``asr_device`` (str): "cpu" or "cuda"
  * ``asr_compute_type`` (str): faster-whisper compute type (e.g., "float16")

These are set via ``extract_to_table(..., ocr_langs=..., deterministic=..., whisper_model=..., ...)``
and also exported to environment variables so optional media extractors can pick
them up consistently:

- UNIFILE_OCR_LANG
- UNIFILE_OCR_LANGS
- UNIFILE_DETERMINISTIC
- UNIFILE_DISABLE_PDF_OCR
- UNIFILE_WHISPER_MODEL
- UNIFILE_ASR_DEVICE
- UNIFILE_ASR_COMPUTE_TYPE
"""

from __future__ import annotations

import os
import asyncio
from importlib import metadata
from pathlib import Path
from typing import List, Optional, Union
import pandas as pd

from unifile.utils.utils import write_temp_file, norm_ext
from unifile.extractors.base import Row
from unifile.processing.manifest import Manifest
from unifile.extractors.pdf_extractor import PdfExtractor
from unifile.extractors.docx_extractor import DocxExtractor
from unifile.extractors.pptx_extractor import PptxExtractor
from unifile.extractors.img_extractor import ImageExtractor
from unifile.extractors.txt_extractor import TextExtractor
from unifile.extractors.html_extractor import HtmlExtractor
from unifile.extractors.xlsx_extractor import ExcelExtractor, CsvExtractor
from unifile.extractors.eml_extractor import EmlExtractor
from unifile.extractors.msg_extractor import MsgExtractor

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
    "ocr_lang": "eng",
    "ocr_langs": "eng",
    "deterministic": False,
    "disable_pdf_ocr": False,  # True when CLI --no-ocr is passed
    # Optional ASR settings (audio/video)
    "asr_model": None,
    "asr_device": None,
    "asr_compute_type": None,
    "table_as_cells": False,
}

def _apply_runtime_env():
    """
    Export the current runtime configuration into environment variables so that
    extractors that read env (e.g., PdfExtractor, Audio/Video ASR backends) see
    consistent settings.
    """
    # OCR
    os.environ["UNIFILE_OCR_LANG"] = _RUNTIME["ocr_lang"] or "eng"
    os.environ["UNIFILE_OCR_LANGS"] = _RUNTIME["ocr_langs"] or _RUNTIME["ocr_lang"] or "eng"
    os.environ["UNIFILE_DETERMINISTIC"] = "1" if _RUNTIME["deterministic"] else ""
    os.environ["UNIFILE_DISABLE_PDF_OCR"] = "1" if _RUNTIME["disable_pdf_ocr"] else ""

    # ASR (optional)
    if _RUNTIME["asr_model"] is not None:
        os.environ["UNIFILE_WHISPER_MODEL"] = str(_RUNTIME["asr_model"])
    if _RUNTIME["asr_device"] is not None:
        os.environ["UNIFILE_ASR_DEVICE"] = str(_RUNTIME["asr_device"])
    if _RUNTIME["asr_compute_type"] is not None:
        os.environ["UNIFILE_ASR_COMPUTE_TYPE"] = str(_RUNTIME["asr_compute_type"])


def set_runtime_options(
    *,
    ocr_lang: Optional[str] = None,
    ocr_langs: Optional[str] = None,
    deterministic: Optional[bool] = None,
    no_ocr: Optional[bool] = None,
    asr_model: Optional[str] = None,
    whisper_model: Optional[str] = None,
    asr_device: Optional[str] = None,
    asr_compute_type: Optional[str] = None,
    table_as_cells: Optional[bool] = None,
) -> None:
    """
    Update in-process runtime options (mirrors CLI flags) and export to env.
    """
    if ocr_langs is not None:
        _RUNTIME["ocr_langs"] = ocr_langs
    if ocr_lang is not None:
        _RUNTIME["ocr_lang"] = ocr_lang
        if ocr_langs is None:
            _RUNTIME["ocr_langs"] = ocr_lang
    if deterministic is not None:
        _RUNTIME["deterministic"] = bool(deterministic)
    if no_ocr is not None:
        _RUNTIME["disable_pdf_ocr"] = bool(no_ocr)

    model = whisper_model if whisper_model is not None else asr_model
    if model is not None:
        _RUNTIME["asr_model"] = model
    if asr_device is not None:
        _RUNTIME["asr_device"] = asr_device
    if asr_compute_type is not None:
        _RUNTIME["asr_compute_type"] = asr_compute_type
    if table_as_cells is not None:
        _RUNTIME["table_as_cells"] = bool(table_as_cells)

    _apply_runtime_env()


# ----------------------------- Registry & factories -----------------------------

# Base registry (pure constructors)
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
    # plain text-ish
    "txt": lambda: TextExtractor(),
    "md": lambda: TextExtractor(),
    "rtf": lambda: TextExtractor(),
    "log": lambda: TextExtractor(),
    # html
    "html": lambda: HtmlExtractor(),
    "htm": lambda: HtmlExtractor(),
    # eml
    "eml":  lambda: EmlExtractor(),
    "msg":  lambda: MsgExtractor(),
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

# Public registry (users/tests may monkeypatch this!)
REGISTRY = REGISTRY_BASE.copy()
SUPPORTED_EXTENSIONS = sorted(REGISTRY.keys())


def load_plugins() -> dict:
    """Discover extractor plugins via entry points.

    Entry points in the ``unifile_extractor.plugins`` group should expose a
    callable that returns a ``dict`` mapping file extensions to extractor
    factory callables. Loaded plugins update :data:`REGISTRY`.
    """
    loaded = {}
    try:
        eps = metadata.entry_points().select(group="unifile_extractor.plugins")
    except Exception:  # pragma: no cover - legacy API
        eps = metadata.entry_points().get("unifile_extractor.plugins", [])
    for ep in eps:
        try:
            plugin = ep.load()
            mapping = plugin()
            if isinstance(mapping, dict):
                loaded.update(mapping)
        except Exception:
            continue
    if loaded:
        REGISTRY.update(loaded)
        global SUPPORTED_EXTENSIONS
        SUPPORTED_EXTENSIONS = sorted(REGISTRY.keys())
    return loaded


def list_plugins() -> List[str]:
    """Return the names of available extractor plugins."""
    try:
        eps = metadata.entry_points().select(group="unifile_extractor.plugins")
    except Exception:  # pragma: no cover
        eps = metadata.entry_points().get("unifile_extractor.plugins", [])
    return sorted(ep.name for ep in eps)


# Load any plugins at import time
load_plugins()


# --------------------------------- Core API -----------------------------------

def detect_extractor(path: Union[str, Path]) -> Optional[str]:
    """
    Determine the extractor to use from a path-like object's extension.
    """
    ext = norm_ext(path)
    return ext if ext in REGISTRY else None


def _rows_to_df(rows: List[Row]) -> pd.DataFrame:
    """
    Convert a list of Row to the standardized pandas DataFrame.
    """
    data = [r.to_dict() for r in rows]
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
    # Image OCR language
    if isinstance(extractor, ImageExtractor):
        try:
            extractor.ocr_langs = _RUNTIME["ocr_langs"] or extractor.ocr_langs
            if hasattr(extractor, "ocr_lang"):
                extractor.ocr_lang = (_RUNTIME["ocr_langs"] or extractor.ocr_langs).split("+")[0]
            extractor.deterministic = _RUNTIME["deterministic"]
        except Exception:
            pass
    # PDF OCR flags
    if isinstance(extractor, PdfExtractor):
        try:
            extractor.ocr_langs = _RUNTIME["ocr_langs"] or extractor.ocr_langs
            if hasattr(extractor, "ocr_lang"):
                extractor.ocr_lang = (_RUNTIME["ocr_langs"] or extractor.ocr_langs).split("+")[0]
            extractor.deterministic = _RUNTIME["deterministic"]
            extractor.ocr_if_empty = not _RUNTIME["disable_pdf_ocr"]
        except Exception:
            pass
    if isinstance(extractor, VideoExtractor):
        try:
            extractor.ocr_langs = _RUNTIME["ocr_langs"] or extractor.ocr_langs
            if hasattr(extractor, "ocr_lang"):
                extractor.ocr_lang = (_RUNTIME["ocr_langs"] or extractor.ocr_langs).split("+")[0]
            extractor.deterministic = _RUNTIME["deterministic"]
        except Exception:
            pass
    if isinstance(extractor, (ExcelExtractor, CsvExtractor)):
        try:
            extractor.as_cells = _RUNTIME["table_as_cells"]
        except Exception:
            pass
    # Other extractors can read env vars already exported in set_runtime_options()


def extract_to_table(
    input_obj: Union[str, Path, bytes],
    *,
    filename: Optional[str] = None,
    # CLI-aligned runtime options (all optional)
    ocr_lang: Optional[str] = None,
    ocr_langs: Optional[str] = None,
    deterministic: Optional[bool] = None,
    no_ocr: Optional[bool] = None,
    asr_model: Optional[str] = None,
    whisper_model: Optional[str] = None,
    asr_device: Optional[str] = None,
    asr_compute_type: Optional[str] = None,
    table_as_cells: Optional[bool] = None,
    manifest: Optional[Manifest] = None,
) -> pd.DataFrame:
    """
    Extract text from a supported file and return a standardized pandas DataFrame.

    If ``manifest`` is provided, a SHA256 hash of ``input_obj`` is recorded
    with its status (``ok``/``error``/``duplicate``) and previously seen hashes
    are skipped.
    """
    # Update runtime config (and environment) from provided options
    set_runtime_options(
        ocr_lang=ocr_lang,
        ocr_langs=ocr_langs,
        deterministic=deterministic,
        no_ocr=no_ocr,
        asr_model=asr_model,
        whisper_model=whisper_model,
        asr_device=asr_device,
        asr_compute_type=asr_compute_type,
        table_as_cells=table_as_cells,
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

    # Instantiate from the current REGISTRY (tests may monkeypatch this)
    factory = REGISTRY[ext]
    extractor = factory()

    # Apply runtime options post-construction (keeps stubs working)
    _apply_runtime_to_instance(extractor)

    if manifest is not None:
        is_dup, _, _ = manifest.check(path)
        if is_dup:
            manifest.record(path, "duplicate")
            return _rows_to_df([])

    rows = extractor.extract(path)

    if manifest is not None:
        status = "ok"
        if any(r.status != "ok" for r in rows):
            status = "error"
        manifest.record(path, status)

    return _rows_to_df(rows)


async def extract_paths(paths: List[Union[str, Path]], **kwargs) -> List[pd.DataFrame]:
    """Asynchronously extract multiple paths.

    Parameters
    ----------
    paths:
        Iterable of file paths to extract. Extraction happens concurrently using
        ``asyncio.to_thread`` since underlying extractors are synchronous.
    **kwargs:
        Optional runtime options forwarded to :func:`extract_to_table`.

    Returns
    -------
    list[pandas.DataFrame]
        A list of standardized DataFrames, one per input path.
    """

    async def _one(p):
        return await asyncio.to_thread(extract_to_table, p, **kwargs)

    coros = [_one(p) for p in paths]
    return await asyncio.gather(*coros)
