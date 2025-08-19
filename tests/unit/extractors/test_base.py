# Copyright (c) 2025 takotime808

import pytest
import json
from pathlib import Path

from unifile.extractors import base


def test_make_row_basic(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")

    row = base.make_row(
        path=f,
        file_type="txt",
        unit_type="file",
        unit_id="body",
        content="hello world",
        metadata={"a": 1},
    )
    assert isinstance(row, base.Row)
    assert row.source_path == str(f)
    assert row.source_name == f.name
    assert row.file_type == "txt"
    assert row.unit_type == "file"
    assert row.unit_id == "body"
    assert row.content == "hello world"
    assert row.char_count == len("hello world")
    assert row.metadata == {"a": 1}
    assert row.status == "ok"
    assert row.error is None


def test_make_row_handles_empty_content_and_metadata(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("")

    row = base.make_row(
        path=f,
        file_type="txt",
        unit_type="file",
        unit_id="0",
        content="",      # empty
        metadata=None,   # None
    )
    assert row.content == ""  # stays empty
    assert row.char_count == 0
    assert row.metadata == {}  # normalized to dict


def test_row_to_dict_with_json_serializable_metadata(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("ok")
    row = base.make_row(f, "txt", "file", "0", "ok", {"key": "value"})
    d = row.to_dict()
    # Metadata should survive roundtrip
    assert d["metadata"] == {"key": "value"}
    # Should be JSON serializable
    json.dumps(d["metadata"])


def test_row_to_dict_with_non_serializable_metadata(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("ok")
    # Put a non-serializable object (like a file handle) into metadata
    class Bad:
        pass
    bad_obj = Bad()
    row = base.make_row(f, "txt", "file", "0", "ok", {"bad": bad_obj})
    d = row.to_dict()
    # Non-serializable replaced with repr dict
    assert "_repr" in d["metadata"]
    assert isinstance(d["metadata"]["_repr"], str)


def test_extractor_protocol_definition():
    """Check that a class implementing Extractor Protocol matches expectations."""
    class DummyExtractor:
        supported_extensions = ["txt"]
        def extract(self, path: Path):
            return []

    # Should satisfy the protocol (not enforced at runtime, but type checkers will)
    ext = DummyExtractor()
    assert hasattr(ext, "supported_extensions")
    assert callable(ext.extract)
    assert isinstance(ext.extract(Path("file.txt")), list)
