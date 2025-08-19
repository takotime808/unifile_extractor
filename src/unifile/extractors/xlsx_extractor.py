# Copyright (c) 2025 takotime808

from __future__ import annotations

from pathlib import Path
from typing import List

import openpyxl
import pandas as pd

from unifile.extractors.base import (
    BaseExtractor,
    make_row,
    Row,
)


class ExcelExtractor(BaseExtractor):
    """
    XLSX/XLS --> plain-text (tab-delimited) extractor.

    This extractor loads a workbook and emits **one row per worksheet**. Each
    worksheet’s cells are serialized as **tab-delimited** lines (one line per
    sheet row), which is convenient for downstream text processing.

    Inherits :meth:`BaseExtractor.extract` for path validation and
    exception-to-error-row wrapping. The actual spreadsheet reading is
    implemented in :meth:`_extract`.

    Supported extensions
    --------------------
    xlsx, xlsm, xltx, xltm, xls

    Output Row (per sheet)
    ----------------------
    - file_type: normalized from the file suffix (e.g., "xlsx")
    - unit_type: "sheet"
    - unit_id:   worksheet title
    - content:   Tab-delimited lines (one per spreadsheet row)
    - metadata:  {"nrows": int, "ncols": int}
    """

    supported_extensions = ["xlsx", "xlsm", "xltx", "xltm", "xls"]

    def _extract(self, path: Path) -> List[Row]:
        """
        Read a workbook and return standardized rows, one per worksheet.

        Parameters
        ----------
        path
            Path to an Excel workbook. Existence checks are handled by
            :class:`BaseExtractor.extract`.

        Returns
        -------
        list[Row]
            Standardized rows for each worksheet.
        """
        rows: List[Row] = []
        # openpyxl doesn't support a context manager on load_workbook; ensure close()
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        try:
            for ws in wb.worksheets:
                lines: list[str] = []
                for row in ws.iter_rows(values_only=True):
                    vals = ["" if v is None else str(v) for v in row]
                    lines.append("\t".join(vals))
                text = "\n".join(lines)
                rows.append(
                    make_row(
                        path=path,
                        file_type=path.suffix.lstrip(".").lower() or "xlsx",
                        unit_type="sheet",
                        unit_id=ws.title,
                        content=text,
                        metadata={"nrows": ws.max_row, "ncols": ws.max_column},
                        status="ok",
                    )
                )
        finally:
            wb.close()
        return rows


class CsvExtractor(BaseExtractor):
    """
    CSV/TSV --> plain-text (CSV serialization) extractor.

    This extractor reads a **CSV** or **TSV** into a pandas DataFrame and emits
    a single row whose `content` is the canonical CSV serialization
    (`df.to_csv(index=False)`), preserving headers and row order.

    Inherits :meth:`BaseExtractor.extract` for path validation and
    exception-to-error-row wrapping. The actual parsing is implemented in
    :meth:`_extract`.

    Supported extensions
    --------------------
    csv, tsv

    Output Row
    ----------
    - file_type: "csv" or "tsv"
    - unit_type: "table"
    - unit_id:   "0"
    - content:   CSV text (comma-separated; TSV is first read with tab sep)
    - metadata:  {"rows": int, "cols": int}
    """

    supported_extensions = ["csv", "tsv"]

    def _extract(self, path: Path) -> List[Row]:
        """
        Parse a CSV/TSV file into a single standardized row.

        Parameters
        ----------
        path
            Path to a `.csv` or `.tsv` file. Existence checks are handled by
            :class:`BaseExtractor.extract`.

        Returns
        -------
        list[Row]
            A single row with CSV text content and basic table metadata.
        """
        sep = "\t" if path.suffix.lower().lstrip(".") == "tsv" else ","
        # dtype=str preserves textual fidelity and avoids dtype inference surprises
        df = pd.read_csv(path, sep=sep, dtype=str)
        text = df.to_csv(index=False)

        return [
            make_row(
                path=path,
                file_type=path.suffix.lstrip(".").lower() or "csv",
                unit_type="table",
                unit_id="0",
                content=text,
                metadata={"rows": len(df), "cols": len(df.columns)},
                status="ok",
            )
        ]
