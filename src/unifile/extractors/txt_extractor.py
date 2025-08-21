# Copyright (c) 2025 takotime808

from __future__ import annotations

from typing import List
from pathlib import Path

from unifile.extractors.base import (
    BaseExtractor,
    make_row,
    Row,
)


class TextExtractor(BaseExtractor):
    """
    Plain-text–style extractor for TXT/MD/RTF/LOG.

    This extractor reads the file as text (using Python's default encoding
    detection fallbacks via ``errors="replace"``) and emits a single
    standardized row.

    Inherits :meth:`BaseExtractor.extract` for path validation and
    exception-to-error-row wrapping. The actual file reading is implemented
    in :meth:`_extract`.

    Supported extensions
    --------------------
    txt, md, rtf, log

    Output Row
    ----------
    - file_type: normalized from the file suffix (e.g., "txt")
    - unit_type: "file"
    - unit_id:   "body"
    - content:   Full text of the file
    - metadata:  {"encoding": "auto"}

    Notes
    -----
    - If you prefer more accurate encoding detection, wire in `chardet` or
      `charset-normalizer` and decode bytes manually before emitting rows.
    """

    supported_extensions = ["txt", "md", "rtf", "log"]

    def _extract(self, path: Path) -> List[Row]:
        """
        Read a text-like file and return a single standardized row.

        Parameters
        ----------
        path
            Path to a supported text-like file. Existence checks are handled by
            :class:`BaseExtractor.extract`.

        Returns
        -------
        list[Row]
            A single row with the file's text content.

        Error Handling
        --------------
        Any unexpected exception raised here would be wrapped by
        :meth:`BaseExtractor.extract` as a single error row. This method
        returns an explicit error row only when you want to customize the error
        payload for known failure modes.
        """
        try:
            text = path.read_text(errors="replace")
        except Exception as e:
            # Optional explicit error row. Alternatively, `raise` and let the
            # BaseExtractor produce a standardized error row automatically.
            return [
                make_row(
                    path=path,
                    file_type="txt",
                    unit_type="file",
                    unit_id="body",
                    content="",
                    metadata={"exc": type(e).__name__},
                    status="error",
                    error=str(e),
                )
            ]

        file_type = path.suffix.lstrip(".").lower() or "txt"
        return [
            make_row(
                path=path,
                file_type=file_type,
                unit_type="file",
                unit_id="body",
                content=text,
                metadata={"encoding": "auto"},
                status="ok",
            )
        ]
