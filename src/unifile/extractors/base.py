# Copyright (c) 2025 takotime808
"""
Base extractor definitions.

This module defines the common `Row` dataclass used to represent extracted
units of text, the `Extractor` protocol that extractor implementations must
conform to, and a `make_row` convenience function.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import (
    List, 
    Optional, 
    Protocol, 
    Sequence,
    # Dict,
    # Iterable,
)


@dataclass
class Row:
    """
    A standardized representation of a single extracted unit of text.

    Attributes
    ----------
    source_path : str
        Absolute or relative path to the source file.
    source_name : str
        Basename of the source file.
    file_type : str
        Normalized file extension (e.g., "pdf", "docx").
    unit_type : str
        Logical unit type, e.g. "page", "slide", "sheet", "file", "image", "table".
    unit_id : str
        Identifier for the unit, such as "0", "1", "Sheet1".
    content : str
        Extracted plain text content.
    char_count : int
        Length of the `content` string in characters.
    metadata : dict
        Arbitrary metadata about the unit (e.g., page index, dimensions).
    status : str
        Extraction status: "ok" or "error".
    error : str | None
        Optional error message if status == "error".
    """
    source_path: str
    source_name: str
    file_type: str
    unit_type: str   # page | slide | sheet | file | image | table
    unit_id: str     # e.g. "0", "1", "Sheet1"
    content: str
    char_count: int
    metadata: dict
    status: str      # "ok" or "error"
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """
        Convert the Row to a JSON-serializable dictionary.

        Notes
        -----
        - If `metadata` contains non-serializable objects, it is replaced
          with a fallback dict: `{"_repr": str(metadata)}`.
        """
        d = asdict(self)
        # ensure metadata is JSON-serializable (best-effort)
        try:
            json.dumps(d["metadata"])
        except Exception:
            d["metadata"] = {"_repr": str(d["metadata"])}
        return d

def make_row(path: Path, file_type: str, unit_type: str, unit_id: str, content: str, metadata: dict, status: str = "ok", error: Optional[str] = None) -> Row:
    """
    Convenience function to create a :class:`Row`.

    Parameters
    ----------
    path : Path
        Path to the source file.
    file_type : str
        Normalized extension (e.g., "pdf").
    unit_type : str
        Logical unit type ("page", "slide", "sheet", etc.).
    unit_id : str
        Identifier for the unit (stringified).
    content : str
        Extracted text content.
    metadata : dict
        Unit-level metadata.
    status : str, default="ok"
        Extraction status.
    error : str | None, default=None
        Error message if status == "error".

    Returns
    -------
    Row
        A populated Row object with `char_count` automatically computed.
    """
    txt = content or ""
    return Row(
        source_path=str(path),
        source_name=path.name,
        file_type=file_type,
        unit_type=unit_type,
        unit_id=str(unit_id),
        content=txt,
        char_count=len(txt),
        metadata=metadata or {},
        status=status,
        error=error,
    )


class Extractor(Protocol):
    """
    Protocol (interface) that all extractors must implement.

    Attributes
    ----------
    supported_extensions : Sequence[str]
        List of file extensions (lowercase, no dot) handled by this extractor.

    Methods
    -------
    extract(path: Path) -> List[Row]
        Perform text extraction from the given file and return standardized rows.
    """
    supported_extensions: Sequence[str]

    def extract(self, path: Path) -> List[Row]:
        ...


class BaseExtractor:
    """
    Optional base class providing a robust `extract()` implementation.

    Subclasses override `_extract(path: Path) -> List[Row]` to do the real work.
    This wrapper:

    * validates the input path (exists + is file),
    * converts unexpected exceptions into a single error `Row`, so callers
      receive a consistent list of `Row` objects instead of an exception.

    Example
    -------
    .. code-block:: python

        class MyTxtExtractor(BaseExtractor):
            supported_extensions = ["txt"]
            def _extract(self, path: Path) -> list[Row]:
                text = path.read_text(errors="replace")
                return [
                    make_row(
                        path,
                        "txt",
                        "file",
                        "body",
                        text,
                        {"encoding": "unknown"},
                    )
                ]
    """

    supported_extensions: Sequence[str] = ()

    def extract(self, path: Path) -> List[Row]:
        """
        Extract text units from `path`.

        Returns
        -------
        list[Row]
            On success: rows with `status="ok"`.
            On failure: a single `Row` with `status="error"` and an `error` message.

        Notes
        -----
        Implementations should override `_extract` rather than this method.
        """
        p = Path(path)
        file_type = (p.suffix.lstrip(".").lower() or "unknown")

        # Basic validation
        if not p.exists() or not p.is_file():
            return [
                make_row(
                    p,
                    file_type=file_type,
                    unit_type="file",
                    unit_id="body",
                    content="",
                    metadata={"reason": "not_found"},
                    status="error",
                    error=f"Not a file: {p}",
                )
            ]

        # Delegate to subclass; wrap unexpected exceptions as an error row
        try:
            rows = self._extract(p)
            # Ensure every returned object looks like a Row
            if not isinstance(rows, list):
                raise TypeError(f"_extract must return List[Row], got {type(rows)}")
            return rows
        except Exception as e:
            return [
                make_row(
                    p,
                    file_type=file_type,
                    unit_type="file",
                    unit_id="body",
                    content="",
                    metadata={"exception": type(e).__name__},
                    status="error",
                    error=str(e),
                )
            ]

    # Subclasses must implement this
    def _extract(self, path: Path) -> List[Row]:  # pragma: no cover - interface method
        raise NotImplementedError("Extractor subclasses must implement _extract()")