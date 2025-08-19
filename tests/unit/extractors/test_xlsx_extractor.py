# Copyright (c) 2025 takotime808

import pytest
import openpyxl
import pandas as pd
from pathlib import Path

from unifile.extractors.xlsx_extractor import ExcelExtractor, CsvExtractor

def _build_xlsx(path: Path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["a","b"])
    ws.append([1,2])
    wb.save(path)

def _build_csv(path: Path):
    df = pd.DataFrame({"x":[1,2],"y":[3,4]})
    df.to_csv(path, index=False)

def test_excel_extractor_reads_sheets(tmp_path):
    p = tmp_path / "sample.xlsx"
    _build_xlsx(p)
    ext = ExcelExtractor()
    rows = ext.extract(p)
    assert rows and rows[0].unit_type == "sheet"
    assert "a\tb" in rows[0].content
    assert rows[0].metadata.get("nrows") >= 2
    assert rows[0].metadata.get("ncols") >= 2

def test_csv_extractor_reads_table(tmp_path):
    p = tmp_path / "sample.csv"
    _build_csv(p)
    ext = CsvExtractor()
    rows = ext.extract(p)
    assert rows and rows[0].unit_type == "table"
    assert "x,y" in rows[0].content.splitlines()[0]
    assert rows[0].metadata.get("rows") == 2
