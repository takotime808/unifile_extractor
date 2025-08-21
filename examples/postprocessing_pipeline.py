# Copyright (c) 2025 takotime808

import langid

from unifile.pipeline import extract_to_table
from unifile.processing.postprocess import (
    clean_whitespace,
    add_language,
    chunk_content,
    summarize,
)


df = extract_to_table("file.epub")  # or a zip, json, etc.
df["content"] = df["content"].map(clean_whitespace)
df = add_language(df, detector=lambda t: langid.classify(t)[0])
chunks = chunk_content(df, max_chars=2000, overlap=100)

def dummy_sum(text: str) -> str: return text[:200] + ("..." if len(text) > 200 else "")
summed = summarize(chunks, summarizer=dummy_sum)