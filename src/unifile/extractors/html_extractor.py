# Copyright (c) 2025 takotime808

from __future__ import annotations

import os
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

def _base_row(source_path:str, unit_type:str, unit_id:int, content:str, file_type:str="html") -> Dict[str,Any]:
    return {
        "source_path": os.path.abspath(source_path),
        "source_name": os.path.basename(source_path),
        "file_type": file_type,
        "unit_type": unit_type,
        "unit_id": unit_id,
        "content": content,
        "char_count": len(content or ""),
        "metadata": {},
        "status": "ok",
        "error": "",
    }

class _SimpleHTMLBlockParser(HTMLParser):
    """
    Very small HTML-to-blocks parser using stdlib only.
    Captures headings <h1..h6>, paragraphs <p>, list items <li>,
    code blocks <code>/<pre>, captions <figcaption>, and tables <table>.
    """
    def __init__(self):
        super().__init__()
        self.blocks: List[Dict[str,Any]] = []
        self._tag_stack: List[str] = []
        self._buf: List[str] = []
        self._unit_id = 0
        self._in_table = False
        self._table_rows: List[List[str]] = []
        self._current_row: List[str] = []
        self._capture_text = False
        self._current_block_type: Optional[str] = None

    def handle_starttag(self, tag, attrs):
        self._tag_stack.append(tag)
        if tag in ("p","li","figcaption"):
            self._buf = []
            self._capture_text = True
            self._current_block_type = {"p":"paragraph","li":"list_item","figcaption":"caption"}[tag]
        elif tag in ("code","pre"):
            self._buf = []
            self._capture_text = True
            self._current_block_type = "code"
        elif tag in ("h1","h2","h3","h4","h5","h6"):
            self._buf = []
            self._capture_text = True
            self._current_block_type = "heading"
        elif tag == "table":
            self._in_table = True
            self._table_rows = []
        elif tag == "tr" and self._in_table:
            self._current_row = []
        elif tag in ("td","th") and self._in_table:
            self._buf = []
            self._capture_text = True
            self._current_block_type = "table_cell"

    def handle_data(self, data):
        if self._capture_text:
            self._buf.append(data)

    def handle_endtag(self, tag):
        # close text blocks
        if tag in ("p","li","figcaption","code","pre","h1","h2","h3","h4","h5","h6"):
            if self._capture_text:
                text = "".join(self._buf).strip()
                if text:
                    self.blocks.append({"block_type": self._current_block_type, "text": text})
                self._buf = []
            self._capture_text = False
            self._current_block_type = None
        # close table cell
        if tag in ("td","th") and self._in_table and self._capture_text:
            text = "".join(self._buf).strip()
            self._current_row.append(text)
            self._buf = []
            self._capture_text = False
            self._current_block_type = None
        # close table row
        if tag == "tr" and self._in_table:
            if self._current_row:
                self._table_rows.append(self._current_row)
            self._current_row = []
        # close table
        if tag == "table" and self._in_table:
            self.blocks.append({"block_type":"table", "table": self._table_rows})
            self._in_table = False

        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

def extract_html(path:str, enable_tables:bool=True, enable_block_types:bool=True) -> List[Dict[str,Any]]:
    """
    Extract HTML into block-level rows. Uses only stdlib HTMLParser to avoid extra deps.
    Tables are emitted as either a single 'table' row with a 2D list in metadata['table'],
    and individual table cells can also be emitted when enable_block_types is True.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    parser = _SimpleHTMLBlockParser()
    parser.feed(content)
    unit_id = 0
    rows: List[Dict[str,Any]] = []
    for b in parser.blocks:
        bt = b.get("block_type")
        if bt == "table":
            if enable_tables:
                row = _base_row(path, "table", unit_id, "\n".join(["\t".join(r) for r in b["table"]]))
                row["metadata"] = {"block_type": "table", "table": b["table"]}
                rows.append(row)
                unit_id += 1
        else:
            text = b.get("text","")
            row = _base_row(path, "block", unit_id, text)
            if enable_block_types:
                row["metadata"] = {"block_type": bt}
            rows.append(row)
            unit_id += 1
    return rows
