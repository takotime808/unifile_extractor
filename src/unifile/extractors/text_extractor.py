# Copyright (c) 2025 takotime808

from __future__ import annotations

import os, re
from typing import Any, Dict, List

def _base_row(source_path:str, unit_type:str, unit_id:int, content:str, file_type:str="txt") -> Dict[str,Any]:
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

def extract_textlike(path:str, enable_block_types:bool=True) -> List[Dict[str,Any]]:
    """
    Extract .txt/.md/.log-like files.
    Heuristics: markdown headings starting with #, list items starting with -/*.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    lines = text.splitlines()
    rows: List[Dict[str,Any]] = []
    unit_id = 0
    heading_rx = re.compile(r"^\s*#{1,6}\s+")
    list_rx = re.compile(r"^\s*[-*+]\s+")
    code_fence_rx = re.compile(r"^\s*```")
    in_code = False

    buf: List[str] = []
    current_type = "paragraph"
    for line in lines + [""]:
        if code_fence_rx.match(line):
            if not in_code:
                # flush previous paragraph
                if buf:
                    rows.append(_make_row(path, unit_id, buf, current_type, enable_block_types))
                    unit_id += 1
                in_code = True
                buf = []
                current_type = "code"
                continue
            else:
                # close code
                rows.append(_make_row(path, unit_id, buf, current_type, enable_block_types))
                unit_id += 1
                in_code = False
                buf = []
                current_type = "paragraph"
                continue

        if in_code:
            buf.append(line)
            continue

        if heading_rx.match(line):
            # flush prev
            if buf:
                rows.append(_make_row(path, unit_id, buf, current_type, enable_block_types))
                unit_id += 1
                buf = []
            current_type = "heading"
            rows.append(_make_row(path, unit_id, [heading_rx.sub("", line).strip()], current_type, enable_block_types))
            unit_id += 1
            current_type = "paragraph"
            continue

        if list_rx.match(line):
            if buf and current_type != "list_item":
                rows.append(_make_row(path, unit_id, buf, current_type, enable_block_types))
                unit_id += 1
                buf = []
            current_type = "list_item"
            rows.append(_make_row(path, unit_id, [list_rx.sub("", line).strip()], current_type, enable_block_types))
            unit_id += 1
            current_type = "paragraph"
            continue

        if line.strip() == "":
            if buf:
                rows.append(_make_row(path, unit_id, buf, current_type, enable_block_types))
                unit_id += 1
                buf = []
                current_type = "paragraph"
            continue

        buf.append(line)

    return rows

def _make_row(path:str, unit_id:int, buf:list[str], block_type:str, enable_block_types:bool) -> Dict[str,Any]:
    text = "\n".join(buf).strip()
    row = _base_row(path, "block", unit_id, text)
    if enable_block_types:
        row["metadata"] = {"block_type": block_type}
    return row
