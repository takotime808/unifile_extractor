# Copyright (c) 2025 takotime808

from pathlib import Path
import types
import json
import pytest

cli = pytest.importorskip("cli_unifile.cli")
import cli_unifile.cli as mod
from .utils_build_samples import build_pdf

def test_cli_url_download_and_extract(tmp_path, monkeypatch):
    # Craft a small PDF in temp and serve its bytes via mocked requests.get
    sample = tmp_path / "sample.pdf"
    build_pdf(sample)
    data = sample.read_bytes()

    class Resp:
        def __init__(self, content): self.content = content
        def raise_for_status(self): pass

    def fake_get(url, timeout=60): return Resp(data)

    requests = pytest.importorskip("requests")
    monkeypatch.setattr(mod, "requests", types.SimpleNamespace(get=fake_get))

    out = tmp_path / "o.jsonl"
    rc = cli.main(["extract", "https://example.com/sample.pdf", "--out", str(out)])
    assert rc == 0 and out.exists()

    # Parse JSONL first line instead of string-matching whitespace
    first_line = out.read_text().splitlines()[0]
    obj = json.loads(first_line)
    assert obj["file_type"] == "pdf"
    assert obj["unit_type"] == "page"
    assert obj["status"] == "ok"

