# Copyright (c) 2025 takotime808

"""Unifile Extractor: unified text extraction to a standardized table."""

__all__ = ["extract_to_table", "ExtractionOptions", "detect_extractor", "SUPPORTED_EXTENSIONS", "version", "write_df", "rag_chunk_df", "export_html"]

from unifile.core import extract_to_table, ExtractionOptions
from unifile.outputs import write_df, rag_chunk_df, export_html

from unifile.pipeline import (
    # extract_to_table,
    detect_extractor,
    SUPPORTED_EXTENSIONS,
)

version = "0.1.0"
__version__ = version

def version() -> str:
    return __version__

