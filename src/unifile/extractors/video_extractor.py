# Copyright (c) 2025 takotime808
"""
Video --> transcript extractor (optional).

Strategy:
  - Extract/convert audio track to mono 16k WAV via ffmpeg
  - Feed WAV to the same ASR backend selection used by AudioExtractor

Requirements (install optional extra):
    pip install ".[media]"

Binary:
    FFmpeg must be available on PATH.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any
import tempfile
import subprocess
import json

from unifile.extractors.audio_extractor import _ASR  # reuse the same backend selection
from unifile.extractors.base import (
    BaseExtractor,
    make_row,
    Row,
)


def _ffmpeg_audio(path: Path) -> Path:
    """Extract audio track to mono 16k WAV with ffmpeg."""
    out_wav = Path(tempfile.mkstemp(prefix="unifile_video_", suffix=".wav")[1])
    subprocess.check_call([
        "ffmpeg", "-y", "-i", str(path),
        "-vn", "-ac", "1", "-ar", "16000",
        str(out_wav)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_wav


def _probe_video(path: Path) -> Dict[str, Any]:
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            stderr=subprocess.STDOUT,
        )
        return json.loads(out.decode("utf-8", errors="replace"))
    except Exception:
        return {}


class VideoExtractor(BaseExtractor):
    """
    Video --> transcript (audio track ASR).

    Supported extensions
    --------------------
    mp4, mov, mkv, webm

    Output Row
    ----------
    - file_type: normalized (e.g., "mp4")
    - unit_type: "video"
    - unit_id:   "0"
    - content:   transcription text (from the primary audio track)
    - metadata:  {"segments":[...], "probe":{...}}
    """

    supported_extensions = ["mp4", "mov", "mkv", "webm"]

    def _extract(self, path: Path) -> List[Row]:
        wav = _ffmpeg_audio(path)
        try:
            text, meta = _ASR.transcribe(wav)
        finally:
            try:
                wav.unlink(missing_ok=True)
            except Exception:
                pass

        probe = _probe_video(path)
        meta["probe"] = {
            "format": (probe.get("format") or {}).get("format_name"),
            "duration": (probe.get("format") or {}).get("duration"),
            "video_streams": [s for s in probe.get("streams", []) if s.get("codec_type") == "video"],
            "audio_streams": [s for s in probe.get("streams", []) if s.get("codec_type") == "audio"],
        }

        return [
            make_row(
                path=path,
                file_type=path.suffix.lstrip(".").lower() or "mp4",
                unit_type="video",
                unit_id="0",
                content=(text or ""),
                metadata=meta,
                status="ok",
            )
        ]
