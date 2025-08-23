import types
import pandas as pd
import unifile.pipeline as pipeline
import cli_unifile.cli as cli

from unifile.extractors.base import Row, make_row

class DummyExtractor:
    supported_extensions = ["foo"]
    def extract(self, path):
        return [make_row(path, "foo", "file", "0", "hi", {}, status="ok")]

def fake_entry_points():
    class EP:
        name = "dummy"
        def load(self):
            return lambda: {"foo": lambda: DummyExtractor()}
    class EPs(list):
        def select(self, group):
            return self if group == "unifile_extractor.plugins" else []
    return EPs([EP()])


def test_load_plugins(monkeypatch):
    monkeypatch.setattr(pipeline.metadata, "entry_points", fake_entry_points)
    pipeline.load_plugins()
    assert "foo" in pipeline.SUPPORTED_EXTENSIONS
    df = pipeline.extract_to_table(b"", filename="a.foo")
    assert df.iloc[0]["file_type"] == "foo"


def test_cli_list_plugins(monkeypatch, capsys):
    monkeypatch.setattr(pipeline.metadata, "entry_points", fake_entry_points)
    cli.main(["plugins"])
    out = capsys.readouterr().out
    assert "dummy" in out
