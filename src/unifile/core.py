# Copyright (c) 2025 takotime808

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import pandas as pd

from unifile.extractors.html_extractor import extract_html
from unifile.extractors.text_extractor import extract_textlike
from unifile.media.asr import transcribe_media
from unifile.metadata import sniff_basic_metadata

# --- Public API options ---
@dataclass
class ExtractionOptions:
    """
    Options to control extraction behavior.

    Attributes
    ----------
    enable_tables : bool
        If True, attempt to extract tables (supported for HTML; other types via optional backends).
    enable_block_types : bool
        If True, annotate row-level 'block_type' in metadata for structural hints (paragraph, heading, list, table_cell, code, caption).
    metadata_mode : str
        One of {"basic","full"} controlling metadata richness. "basic" collects file stats; "full" attempts deep metadata when supported.
    asr_backend : str
        For audio/video: one of {"auto","dummy","whisper","faster-whisper","whispercpp"}.
    media_chunk_seconds : int
        Target chunk duration (seconds) for streaming ASR backends.
    """
    enable_tables: bool = True
    enable_block_types: bool = True
    metadata_mode: str = "basic"
    asr_backend: str = "auto"
    media_chunk_seconds: int = 30


# --- helpers ---
def _empty_df() -> pd.DataFrame:
    cols = ["source_path","source_name","file_type","unit_type","unit_id",
            "content","char_count","metadata","status","error"]
    return pd.DataFrame(columns=cols)


def _make_row(source_path:str, unit_type:str, unit_id:Union[int,str], content:str,
              file_type:str, status:str="ok", error:str="") -> Dict[str,Any]:
    base = os.path.basename(source_path)
    return {
        "source_path": os.path.abspath(source_path),
        "source_name": base,
        "file_type": file_type.lower(),
        "unit_type": unit_type,
        "unit_id": unit_id,
        "content": content,
        "char_count": len(content or ""),
        "metadata": {},
        "status": status,
        "error": error,
    }


# --- Router ---
_TEXT_EXTS = {".txt",".md",".rtf",".log"}
_HTML_EXTS = {".html",".htm"}
_MEDIA_EXTS = {".wav",".mp3",".m4a",".flac",".ogg",".webm",".aac",".mp4",".mov",".mkv"}

def extract_to_table(path_or_bytes: Union[str, bytes, io.BytesIO],
                     filename: Optional[str]=None,
                     options: Optional[ExtractionOptions]=None) -> pd.DataFrame:
    """
    Extract text (and optionally tables/layout metadata) into the standard DataFrame schema.

    Parameters
    ----------
    path_or_bytes : str | bytes | io.BytesIO
        Either a filesystem path/URL or raw bytes-like object.
    filename : str, optional
        Required when passing bytes to help sniff file type.
    options : ExtractionOptions, optional
        Controls tables, block typing, metadata richness, and media backend.

    Returns
    -------
    pandas.DataFrame
        Rows with columns: source_path, source_name, file_type, unit_type, unit_id,
        content, char_count, metadata, status, error.
    """
    options = options or ExtractionOptions()

    # Handle bytes input by saving to a temporary in-memory buffer/virtual path.
    is_bytes = isinstance(path_or_bytes, (bytes, io.BytesIO))
    if is_bytes and not filename:
        raise ValueError("filename is required when extracting from bytes")
    if is_bytes:
        # For our simple implementation, write bytes to a temporary file so we can reuse path-based logic.
        # In production, you might carry a virtual path and avoid I/O.
        tmp_path = f"/tmp/unifile_{os.getpid()}_{abs(hash(filename))}"
        with open(tmp_path, "wb") as f:
            f.write(path_or_bytes if isinstance(path_or_bytes, bytes) else path_or_bytes.read())
        source_path = tmp_path
        inferred_name = filename
    else:
        source_path = str(path_or_bytes)
        inferred_name = os.path.basename(source_path)

    ext = os.path.splitext(inferred_name)[1].lower()
    rows: List[Dict[str,Any]] = []

    try:
        if ext in _HTML_EXTS:
            rows = extract_html(source_path, enable_tables=options.enable_tables, enable_block_types=options.enable_block_types)
        elif ext in _TEXT_EXTS:
            rows = extract_textlike(source_path, enable_block_types=options.enable_block_types)
        elif ext in _MEDIA_EXTS:
            rows = transcribe_media(source_path, backend=options.asr_backend, chunk_seconds=options.media_chunk_seconds)
        else:
            # Fallback – read as text if possible
            try:
                with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                rows = [ _make_row(source_path, "file", 0, text, file_type=ext.lstrip(".")) ]
            except Exception as e:
                rows = [ _make_row(source_path, "file", 0, "", file_type=ext.lstrip("."), status="error", error=str(e)) ]

        # Annotate metadata and ensure schema
        file_type = ext.lstrip(".")
        for r in rows:
            md = sniff_basic_metadata(source_path, mode=options.metadata_mode)
            # merge but don't overwrite row-level metadata if present
            r["metadata"] = {**md, **(r.get("metadata") or {})}
            r["file_type"] = file_type

        df = pd.DataFrame(rows)
        # enforce column order/superset
        cols = ["source_path","source_name","file_type","unit_type","unit_id","content","char_count","metadata","status","error"]
        for c in cols:
            if c not in df.columns:
                df[c] = None
        return df[cols]
    finally:
        # Clean up ephemeral temp file created for bytes input
        if is_bytes:
            try:
                os.remove(source_path)
            except Exception:
                pass
