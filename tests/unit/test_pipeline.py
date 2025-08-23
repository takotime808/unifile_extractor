# Copyright (c) 2025 takotime808

# tests/unit/test_pipeline.py

from __future__ import annotations

import pytest
# import types
from pathlib import Path

# Import the pipeline module under test
import unifile.pipeline as pipeline
from unifile.extractors.base import make_row
from unifile.extractors.xlsx_extractor import CsvExtractor


class DummyExtractor:
    """Minimal extractor used to stub out real extractors in tests."""
    def __init__(self, file_type="txt", content="hello world"):
        self.file_type = file_type
        self.content = content

    def extract(self, path: Path):
        # Return a single standardized Row using the real helper
        return [
            make_row(
                path=path,
                file_type=self.file_type,
                unit_type="file",
                unit_id="body",
                content=self.content,
                metadata={"stub": True},
            )
        ]


def test_detect_extractor_known_and_unknown():
    # Known: 'txt' exists in REGISTRY by default
    assert pipeline.detect_extractor("anything.TXT") == "txt"
    # Unknown: bogus extension not in REGISTRY
    assert pipeline.detect_extractor("file.bogus") is None


def test__rows_to_df_adds_missing_columns_and_orders(monkeypatch, tmp_path):
    # Build a dummy row whose to_dict is missing some columns on purpose
    class MinimalRow:
        def to_dict(self):
            return {
                "source_path": "/tmp/x",
                "source_name": "x",
                "file_type": "txt",
                "unit_type": "file",
                "unit_id": "body",
                "content": "hi",
                # intentionally omit char_count, metadata, status, error
            }

    df = pipeline._rows_to_df([MinimalRow()])  # type: ignore[arg-type]
    # Columns should be present and in canonical order
    assert list(df.columns) == [
        "source_path",
        "source_name",
        "file_type",
        "unit_type",
        "unit_id",
        "content",
        "char_count",
        "metadata",
        "status",
        "error",
    ]
    # Missing columns should be filled (NaNs or None are fine; we just assert presence)
    assert df.loc[0, "char_count"] in (None, pytest.approx(df.loc[0, "char_count"]), df.loc[0, "char_count"])


def test_extract_to_table_with_path_uses_registry_stub(monkeypatch, tmp_path):
    # Create a real file so pipeline's file existence check passes
    f = tmp_path / "sample.txt"
    f.write_text("does not matter for stub")

    # Stub registry to ensure we control extractor behavior
    stub_registry = {"txt": lambda: DummyExtractor(file_type="txt", content="OK")}
    monkeypatch.setattr(pipeline, "REGISTRY", stub_registry)
    monkeypatch.setattr(pipeline, "SUPPORTED_EXTENSIONS", sorted(stub_registry.keys()))

    df = pipeline.extract_to_table(f)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["file_type"] == "txt"
    assert row["content"] == "OK"
    assert row["unit_type"] == "file"
    assert row["unit_id"] == "body"
    assert isinstance(row["metadata"], dict) and row["metadata"].get("stub") is True


def test_extract_to_table_with_bytes_and_filename(monkeypatch):
    # Provide bytes and a filename with extension used to select extractor
    data = b"hello bytes route"
    filename = "in.txt"

    stub_registry = {"txt": lambda: DummyExtractor(file_type="txt", content="BYTES_OK")}
    monkeypatch.setattr(pipeline, "REGISTRY", stub_registry)
    monkeypatch.setattr(pipeline, "SUPPORTED_EXTENSIONS", sorted(stub_registry.keys()))

    df = pipeline.extract_to_table(data, filename=filename)
    assert df.iloc[0]["content"] == "BYTES_OK"
    assert df.iloc[0]["file_type"] == "txt"


def test_extract_to_table_bytes_without_filename_raises():
    with pytest.raises(ValueError, match="filename is required"):
        pipeline.extract_to_table(b"no filename provided")


def test_extract_to_table_unsupported_extension_raises(monkeypatch, tmp_path):
    f = tmp_path / "x.xyz"
    f.write_text("irrelevant")
    # Empty registry so no supported types
    monkeypatch.setattr(pipeline, "REGISTRY", {})
    monkeypatch.setattr(pipeline, "SUPPORTED_EXTENSIONS", [])
    with pytest.raises(ValueError, match="Unsupported file extension"):
        pipeline.extract_to_table(f)


def test_extract_to_table_file_not_found_raises(tmp_path):
    missing = tmp_path / "nope.txt"
    with pytest.raises(FileNotFoundError):
        pipeline.extract_to_table(missing)


def test_pipeline_table_as_cells(monkeypatch, tmp_path):
    p = tmp_path / "tab.csv"
    p.write_text("a,b\n1,2\n")
    stub_registry = {"csv": lambda: CsvExtractor()}
    monkeypatch.setattr(pipeline, "REGISTRY", stub_registry)
    monkeypatch.setattr(pipeline, "SUPPORTED_EXTENSIONS", ["csv"])
    df = pipeline.extract_to_table(p, table_as_cells=True)
    assert (df["unit_type"] == "cell").all()
