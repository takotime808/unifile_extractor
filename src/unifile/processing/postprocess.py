# Copyright (c) 2025 takotime808

from __future__ import annotations

from typing import Callable
import re
import pandas as pd

def clean_whitespace(text: str) -> str:
    if not isinstance(text, str): return ""
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"\s+\Z", "", text)).replace("\r\n", "\n").replace("\r", "\n")

def add_language(df: pd.DataFrame, detector: Callable[[str], str]) -> pd.DataFrame:
    # Adds 'lang' column using a user-provided detector, e.g., langid.classify
    langs = []
    for t in df["content"]:
        try:
            langs.append(detector(t or "") or "")
        except Exception:
            langs.append("")
    df2 = df.copy()
    df2["lang"] = langs
    return df2

def chunk_content(df: pd.DataFrame, max_chars: int = 4000, overlap: int = 200) -> pd.DataFrame:
    # Splits each row's content into chunks; preserves all metadata; adds chunk_id
    rows = []
    for _, r in df.iterrows():
        text = r["content"] or ""
        start = 0; i = 0
        while start < len(text):
            end = min(len(text), start + max_chars)
            chunk = text[start:end]
            rr = r.copy()
            rr["content"] = chunk
            rr["char_count"] = len(chunk)
            rr["unit_type"] = f"{r['unit_type']}:chunk"
            rr["unit_id"] = f"{r['unit_id']}:{i}"
            rows.append(rr)
            i += 1
            start = end - overlap
            if start < 0: start = 0
    return pd.DataFrame(rows, columns=df.columns)

def summarize(df: pd.DataFrame, summarizer: Callable[[str], str], max_chars: int = 6000) -> pd.DataFrame:
    # New dataframe with 'summary' column; leaves original content intact
    out = df.copy()
    out["summary"] = [
        summarizer((c or "")[:max_chars]) if isinstance(c, str) else "" for c in out["content"]
    ]
    return out
