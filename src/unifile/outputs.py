# Copyright (c) 2025 takotime808

from __future__ import annotations

import os
import json
import sqlite3
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

def write_df(df: pd.DataFrame, out_path: str, table: str="unifile") -> None:
    """
    Write a DataFrame to a sink inferred from out_path extension.
    Supported: .csv, .jsonl, .sqlite, .parquet (if pyarrow/fastparquet installed).
    """
    out_path = str(out_path)
    ext = os.path.splitext(out_path)[1].lower()
    Path(os.path.dirname(out_path) or ".").mkdir(parents=True, exist_ok=True)

    if ext == ".csv":
        df.to_csv(out_path, index=False)
    elif ext in (".jsonl",".json"):
        with open(out_path, "w", encoding="utf-8") as f:
            for _, row in df.iterrows():
                f.write(json.dumps(_jsonable(row.to_dict()), ensure_ascii=False) + "\n")
    elif ext == ".sqlite":
        def _to_sqlite(v: Any) -> Any:
            if isinstance(v, (dict, list)):
                return json.dumps(_jsonable(v), ensure_ascii=False)
            return v

        df_sql = df.applymap(_to_sqlite)
        con = sqlite3.connect(out_path)
        try:
            df_sql.to_sql(table, con, if_exists="replace", index=False)
        finally:
            con.close()
    elif ext == ".parquet":
        try:
            df.to_parquet(out_path, index=False)
        except Exception as e:
            raise RuntimeError("Parquet support requires 'pyarrow' or 'fastparquet' to be installed") from e
    else:
        raise ValueError(f"Unsupported output extension: {ext}")

def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k,v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    # Leave other types to json.dumps; ensure non-serializable objects are stringified
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        return str(obj)

def rag_chunk_df(df: pd.DataFrame, target_chars:int=1000, overlap:int=100) -> pd.DataFrame:
    """
    Split rows into RAG-friendly chunks by character count.
    Emits additional rows with unit_type='chunk' and metadata['parent_unit'] pointing to the original (unit_type, unit_id).
    """
    rows: List[Dict[str,Any]] = []
    for _, r in df.iterrows():
        text = str(r.get("content",""))
        parent = {"parent_unit_type": r.get("unit_type"), "parent_unit_id": r.get("unit_id")}
        i = 0
        start = 0
        while start < len(text):
            end = min(len(text), start + target_chars)
            chunk = text[start:end]
            nr = r.to_dict()
            nr["unit_type"] = "chunk"
            nr["unit_id"] = f"{r.get('unit_id')}:{i}"
            nr["content"] = chunk
            md = dict(r.get("metadata") or {})
            md.update(parent)
            nr["metadata"] = md
            nr["char_count"] = len(chunk)
            rows.append(nr)
            i += 1
            start = end - overlap if end - overlap > start else end
    return pd.DataFrame(rows, columns=df.columns)

def export_html(df: pd.DataFrame, out_path: str, title: str="Unifile Export") -> None:
    """
    Export rows to a simple HTML document preserving block/table boundaries.
    """
    html_parts = [f"<html><head><meta charset='utf-8'><title>{title}</title></head><body>"]
    curr_source = None
    for _, r in df.iterrows():
        if r["source_name"] != curr_source:
            if curr_source is not None:
                html_parts.append("<hr/>")
            html_parts.append(f"<h2>File: {r['source_name']}</h2>")
            curr_source = r["source_name"]
        bt = (r.get("metadata") or {}).get("block_type")
        if r["unit_type"] == "table":
            html_parts.append("<div class='table'><pre>")
            html_parts.append((r["content"] or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"))
            html_parts.append("</pre></div>")
        elif bt == "heading":
            html_parts.append(f"<h3>{r['content']}</h3>")
        elif bt == "list_item":
            html_parts.append(f"<li>{r['content']}</li>")
        elif bt == "code":
            html_parts.append("<pre><code>")
            html_parts.append((r["content"] or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"))
            html_parts.append("</code></pre>")
        else:
            html_parts.append(f"<p>{r['content']}</p>")
    html_parts.append("</body></html>")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))
