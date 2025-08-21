# Copyright (c) 2025 takotime808

import pytest

cli = pytest.importorskip("unifile.cli")
from .utils_build_samples import build_txt, build_pdf

def test_cli_extract_prints_stdout(tmp_path, capsys, monkeypatch):
    # build a txt file and run CLI main without --out
    p = tmp_path / "s.txt"
    build_txt(p)
    rc = cli.main(["extract", str(p), "--max-rows", "10", "--max-colwidth", "60"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "s.txt" in out
    assert "hello" in out

def test_cli_extract_writes_csv(tmp_path):
    p = tmp_path / "s.pdf"
    build_pdf(p)
    out = tmp_path / "t.csv"
    rc = cli.main(["extract", str(p), "--out", str(out)])
    assert rc == 0
    assert out.exists()
    # file has header
    text = out.read_text()
    assert "source_path,source_name,file_type" in text
