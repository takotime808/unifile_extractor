# Copyright (c) 2025 takotime808
"""
Unified extraction pipeline.

This module wires file extensions to concrete extractor implementations and exposes
two key utilities:

- ``detect_extractor(path)``: resolve the normalized extension and return it only
  if it’s supported by the registry.
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
"""


from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union
import pandas as pd

from unifile.utils.utils import write_temp_file, norm_ext
from unifile.extractors.base import Row
from unifile.extractors.pdf_extractor import PdfExtractor
from unifile.extractors.docx_extractor import DocxExtractor
from unifile.extractors.pptx_extractor import PptxExtractor
from unifile.extractors.img_extractor import ImageExtractor
from unifile.extractors.txt_extractor import TextExtractor
from unifile.extractors.html_extractor import HtmlExtractor
from unifile.extractors.xlsx_extractor import ExcelExtractor, CsvExtractor

# Registry maps extension -> a callable returning an extractor instance
REGISTRY = {
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
}

SUPPORTED_EXTENSIONS = sorted(REGISTRY.keys())

def detect_extractor(path: Union[str, Path]) -> Optional[str]:
    """
    Determine the extractor to use from a path-like object’s extension.

    Parameters
    ----------
    path
        Any string or :class:`pathlib.Path`. Existence on disk is **not** required.

    Returns
    -------
    str | None
        The normalized extension (e.g., ``"pdf"``) when supported; otherwise ``None``.

    Examples
    --------
    >>> detect_extractor("file.TXT")
    'txt'
    >>> detect_extractor("report.unknown") is None
    True
    """
    ext = norm_ext(path)
    return ext if ext in REGISTRY else None

def _rows_to_df(rows: List[Row]) -> pd.DataFrame:
    """
    Convert a list of :class:`Row` to the standardized pandas DataFrame.

    Any missing columns are added and ordered in the canonical schema.

    Parameters
    ----------
    rows
        A list of :class:`Row` instances (or row-like objects with ``to_dict()``).

    Returns
    -------
    pandas.DataFrame
        DataFrame with columns in this exact order:
        ``["source_path", "source_name", "file_type", "unit_type", "unit_id",
        "content", "char_count", "metadata", "status", "error"]``.
    """
    data = [r.to_dict() for r in rows]
    cols = ["source_path", "source_name", "file_type", "unit_type", "unit_id", "content", "char_count", "metadata", "status", "error"]
    df = pd.DataFrame(data)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]

def extract_to_table(input_obj: Union[str, Path, bytes], *, filename: Optional[str] = None) -> pd.DataFrame:
    """Extract text from a supported file and return a standardized pandas DataFrame.

    Parameters
    ----------
    input_obj : str | Path | bytes
        Path to a file on disk, or a bytes object representing file contents.
    filename : str | None
        Required if input_obj is bytes. Used to determine file type by extension.

    Returns
    -------
    pandas.DataFrame
        Standardized table with columns:
        [source_path, source_name, file_type, unit_type, unit_id, content, char_count, metadata, status, error].
    """
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
        raise ValueError(f"Unsupported file extension '{path.suffix}'. Supported: {', '.join(SUPPORTED_EXTENSIONS)}")

    extractor = REGISTRY[ext]()  # instantiate
    rows = extractor.extract(path)
    return _rows_to_df(rows)
