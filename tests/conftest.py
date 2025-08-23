# Copyright (c) 2025 takotime808

import io
import os
import sys
from pathlib import Path
import pytest

# Ensure local src on sys.path if running from a source checkout layout like unifile_extractor/src
def _maybe_add_src_to_path():
    here = Path(__file__).resolve()
    # Try common layouts
    candidates = [
        here.parents[1] / "src",              # repo_root/src when conftest in tests/
        here.parents[2] / "src",              # repo_root/src
        here.parents[3] / "src",              # when tests/ under repo_root/tests/unit
    ]
    for c in candidates:
        if c.exists() and str(c) not in sys.path:
            sys.path.insert(0, str(c))

_maybe_add_src_to_path()

@pytest.fixture
def tmpdir(tmp_path):
    return tmp_path

@pytest.fixture
def simple_html(tmp_path):
    p = tmp_path / "sample.html"
    p.write_text(
        "<html><head><title>T</title></head><body><h1>Header</h1>"
        "<p>Hello <b>world</b>! Visit <a href='https://example.com'>Example</a></p>"
        "</body></html>"
    )
    return p

@pytest.fixture
def simple_txt(tmp_path):
    p = tmp_path / "sample.txt"
    p.write_text("hello\nworld\n")
    return p
