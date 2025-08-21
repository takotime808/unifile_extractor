# Copyright (c) 2025 takotime808

import pytest
# from pathlib import Path

try:
    from unifile.pipeline import extract_to_table
except Exception:
    pytest.skip("unifile.pipeline not importable", allow_module_level=True)

from .utils_build_samples import build_txt

def test_schema_columns_order(tmp_path):
    p = tmp_path / "a.txt"
    build_txt(p)
    df = extract_to_table(p)
    assert list(df.columns) == [
        "source_path","source_name","file_type","unit_type","unit_id","content","char_count","metadata","status","error"
    ]
