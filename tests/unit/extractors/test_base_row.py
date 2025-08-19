# Copyright (c) 2025 takotime808

import pytest
import json
from unifile.extractors.base import make_row
# from pathlib import Path

def test_make_row_dict_serializable(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("x")
    row = make_row(p, "txt", "file", "body", "content", {"a": 1})
    d = row.to_dict()
    assert d["file_type"] == "txt"
    assert d["unit_type"] == "file"
    assert d["unit_id"] == "body"
    assert d["char_count"] == len("content")
    assert d["status"] == "ok"
    # metadata must be JSON serializable
    json.dumps(d["metadata"])
