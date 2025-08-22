# Copyright (c) 2025 takotime808

import json
import pytest
import sqlite3
import pandas as pd

from unifile import extract_to_table, ExtractionOptions
from unifile.outputs import write_df, rag_chunk_df, export_html
from unifile.media.asr import export_srt, export_vtt, Segment

def test_dummy_asr_and_subtitle_exports(tmp_path):
    # Create a small dummy "media" file (extension .mp3)
    p = tmp_path / "audio.mp3"
    p.write_bytes(b"0" * 50000)  # 50KB

    df = extract_to_table(str(p), options=ExtractionOptions(asr_backend="dummy", media_chunk_seconds=10))
    assert all(df.unit_type == "segment")
    # build SRT/VTT from segments created by dummy transcriber
    segments = [Segment(r.metadata["start"], r.metadata["end"], r.content) for _, r in df.iterrows()]
    srt = export_srt(segments)
    vtt = export_vtt(segments)
    assert "WEBVTT" in vtt.splitlines()[0]
    assert "-->" in srt
    assert "[dummy transcript segment 0]" in srt

def test_sinks_and_rag_chunking(tmp_path):
    # Create a simple df
    import pandas as pd
    df = pd.DataFrame([
        {"source_path":"/x/a.txt","source_name":"a.txt","file_type":"txt","unit_type":"block","unit_id":0,"content":"a"*1500,"char_count":1500,"metadata":{},"status":"ok","error":""},
        {"source_path":"/x/a.txt","source_name":"a.txt","file_type":"txt","unit_type":"block","unit_id":1,"content":"b"*300,"char_count":300,"metadata":{},"status":"ok","error":""},
    ])
    # RAG chunking
    chunks = rag_chunk_df(df, target_chars=500, overlap=50)
    assert all(chunks.unit_type == "chunk")
    assert any(":1" in str(uid) for uid in chunks.unit_id)

    # CSV
    out_csv = tmp_path / "out.csv"
    write_df(chunks, str(out_csv))
    assert out_csv.exists() and out_csv.read_text(encoding="utf-8").startswith("source_path")

    # JSONL
    out_jsonl = tmp_path / "out.jsonl"
    write_df(chunks, str(out_jsonl))
    with open(out_jsonl, "r", encoding="utf-8") as f:
        first = json.loads(f.readline())
    assert "unit_type" in first

    # SQLite
    out_sqlite = tmp_path / "out.sqlite"
    write_df(chunks, str(out_sqlite), table="data")
    con = sqlite3.connect(out_sqlite)
    try:
        cur = con.execute("select count(*) from data")
        n, = cur.fetchone()
        assert n == len(chunks)
    finally:
        con.close()

def test_export_html(tmp_path):
    # Build a small df with block types and a table
    df = pd.DataFrame([
        {"source_path":"/x/index.html","source_name":"index.html","file_type":"html","unit_type":"block","unit_id":0,"content":"Intro","char_count":5,"metadata":{"block_type":"paragraph"},"status":"ok","error":""},
        {"source_path":"/x/index.html","source_name":"index.html","file_type":"html","unit_type":"table","unit_id":1,"content":"A\tB\n1\t2","char_count":7,"metadata":{"block_type":"table"},"status":"ok","error":""},
    ])
    out = tmp_path / "doc.html"
    export_html(df, str(out), title="Demo")
    txt = out.read_text(encoding="utf-8")
    assert "<h2>File: index.html</h2>" in txt
    assert "<pre>" in txt and "A\tB" in txt
