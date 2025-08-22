# Copyright (c) 2025 takotime808

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List

def _base_row(source_path:str, unit_id:int, text:str, status:str="ok", error:str="") -> Dict[str,Any]:
    return {
        "source_path": os.path.abspath(source_path),
        "source_name": os.path.basename(source_path),
        "file_type": os.path.splitext(source_path)[1].lstrip(".").lower(),
        "unit_type": "segment",
        "unit_id": unit_id,
        "content": text,
        "char_count": len(text or ""),
        "metadata": {},
        "status": status,
        "error": error,
    }

@dataclass
class Segment:
    start: float
    end: float
    text: str

def _dummy_transcribe(path:str, chunk_seconds:int=30) -> List[Segment]:
    """
    A deterministic, dependency-free "ASR" that pretends each 32KB is one chunk and emits text.
    Intended for testing and CI. Not a real transcription.
    """
    sz = os.stat(path).st_size
    # approx bytes per "second", just to synthesize timestamps
    bps = 16000
    segments: List[Segment] = []
    num_chunks = max(1, (sz + (bps*chunk_seconds) - 1) // (bps*chunk_seconds))
    for i in range(int(num_chunks)):
        start = i * chunk_seconds
        end = (i+1) * chunk_seconds
        segments.append(Segment(start, end, f"[dummy transcript segment {i}]"))
    return segments

def transcribe_media(path:str, backend:str="auto", chunk_seconds:int=30) -> List[Dict[str,Any]]:
    """
    Transcribe audio/video into 'segment' rows.
    Backends:
      - auto: falls back to 'dummy' in this minimal implementation.
      - dummy: emits synthetic segments based on file size and chunk_seconds.
      - whisper / faster-whisper / whispercpp: placeholders (require optional deps in real project).
    """
    b = backend or "auto"
    if b in ("auto","dummy","whisper","faster-whisper","whispercpp"):
        segs = _dummy_transcribe(path, chunk_seconds=chunk_seconds)
    else:
        segs = _dummy_transcribe(path, chunk_seconds=chunk_seconds)

    rows: List[Dict[str,Any]] = []
    for i, s in enumerate(segs):
        r = _base_row(path, i, s.text)
        r["metadata"] = {"start": s.start, "end": s.end, "asr_backend": b if b!="auto" else "dummy"}
        rows.append(r)
    return rows

def export_srt(segments: List[Segment]) -> str:
    """Create SRT formatted string from segments."""
    def fmt(t:float) -> str:
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t - int(t)) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    lines = []
    for i, seg in enumerate(segments, start=1):
        lines.append(str(i))
        lines.append(f"{fmt(seg.start)} --> {fmt(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)

def export_vtt(segments: List[Segment]) -> str:
    """Create VTT formatted string from segments."""
    def fmt(t:float) -> str:
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t - int(t)) * 1000)
        return f"{h:02}:{m:02}:{s:02}.{ms:03}"
    lines = ["WEBVTT",""]
    for seg in segments:
        lines.append(f"{fmt(seg.start)} --> {fmt(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)
