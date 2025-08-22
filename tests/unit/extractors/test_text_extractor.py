# Copyright (c) 2025 takotime808

import pytest

from unifile import extract_to_table, ExtractionOptions

def test_text_block_types(tmp_path):
    txt = "# Heading\n\nParagraph line one.\n\n- item one\n- item two\n\n```\ncode fence\n```"
    p = tmp_path / "sample.md"
    p.write_text(txt, encoding="utf-8")
    df = extract_to_table(str(p), options=ExtractionOptions(enable_block_types=True))
    btypes = [ (r.get("metadata") or {}).get("block_type") for _, r in df.iterrows() ]
    assert "heading" in btypes
    assert "list_item" in btypes
    assert "code" in btypes
    assert "paragraph" in btypes
