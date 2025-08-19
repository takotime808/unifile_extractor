# Copyright (c) 2025 takotime808

from __future__ import annotations

import openpyxl
import pandas as pd
from pathlib import Path
from typing import List

from unifile.extractors.base import (
    # Extractor,
    make_row,
    Row,
)

class ExcelExtractor:
    supported_extensions = ["xlsx", "xlsm", "xltx", "xltm", "xls"]

    def extract(self, path: Path) -> List[Row]:
        rows: List[Row] = []
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        for ws in wb.worksheets:
            lines = []
            for row in ws.iter_rows(values_only=True):
                vals = ["" if v is None else str(v) for v in row]
                lines.append("\t".join(vals))
            text = "\n".join(lines)
            rows.append(make_row(path, path.suffix.lstrip('.').lower(), "sheet", ws.title, text, {"nrows": ws.max_row, "ncols": ws.max_column}))
        return rows

class CsvExtractor:
    supported_extensions = ["csv", "tsv"]

    def extract(self, path: Path) -> List[Row]:
        sep = "\t" if path.suffix.lower().lstrip('.') == "tsv" else ","
        df = pd.read_csv(path, sep=sep, dtype=str)
        text = df.to_csv(index=False)
        return [make_row(path, path.suffix.lstrip('.').lower(), "table", "0", text, {"rows": len(df), "cols": len(df.columns)})]
