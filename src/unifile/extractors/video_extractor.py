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
from typing import List, Dict, Any, Tuple
import tempfile
import subprocess
import json
import os
import random

from PIL import Image
import pytesseract

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


def _ffmpeg_frames(path: Path, interval: float) -> List[Tuple[Path, float]]:
    """Sample video frames every ``interval`` seconds."""
    tmpdir = Path(tempfile.mkdtemp(prefix="unifile_frames_"))
    pattern = tmpdir / "frame_%06d.png"
    subprocess.check_call([
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-vf",
        f"fps=1/{interval}",
        str(pattern),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    frames = sorted(tmpdir.glob("frame_*.png"))
    return [(fp, i * interval) for i, fp in enumerate(frames)]


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
    """Extract text and transcripts from video files.

    The extractor performs two passes:

    1. Audio transcription using Whisper (via :mod:`audio_extractor`).
    2. Keyframe OCR sampling frames every ``frame_interval`` seconds.

    Each sampled frame produces a row with ``unit_type="frame"`` and
    ``metadata['timestamp']`` indicating the capture time.
    """

    supported_extensions = ["mp4", "mov", "mkv", "webm"]

    def __init__(self, frame_interval: float = 5.0, ocr_langs: str = "eng", deterministic: bool = False):
        self.frame_interval = frame_interval
        self.ocr_langs = ocr_langs
        self.deterministic = deterministic

    def _ocr_image(self, img: Image.Image) -> str:
        config = "--dpi 300" if self.deterministic else ""
        return pytesseract.image_to_string(img, lang=self.ocr_langs, config=config) or ""

    def _extract(self, path: Path) -> List[Row]:
        env_langs = os.getenv("UNIFILE_OCR_LANGS")
        if env_langs:
            self.ocr_langs = env_langs
        if os.getenv("UNIFILE_DETERMINISTIC"):
            self.deterministic = True
        if self.deterministic:
            random.seed(0)

        wav = _ffmpeg_audio(path)
        try:
            text, meta = _ASR.transcribe(wav)
        finally:
            try:
                wav.unlink(missing_ok=True)
            except Exception:
                pass

        rows: List[Row] = []

        probe = _probe_video(path)
        meta["probe"] = {
            "format": (probe.get("format") or {}).get("format_name"),
            "duration": (probe.get("format") or {}).get("duration"),
            "video_streams": [s for s in probe.get("streams", []) if s.get("codec_type") == "video"],
            "audio_streams": [s for s in probe.get("streams", []) if s.get("codec_type") == "audio"],
        }

        rows.append(
            make_row(
                path=path,
                file_type=path.suffix.lstrip(".").lower() or "mp4",
                unit_type="video",
                unit_id="0",
                content=(text or ""),
                metadata=meta,
                status="ok",
            )
        )

        frames = _ffmpeg_frames(path, self.frame_interval)
        try:
            for idx, (fp, ts) in enumerate(frames):
                with Image.open(fp) as img:
                    frame_text = self._ocr_image(img)
                    rows.append(
                        make_row(
                            path=path,
                            file_type=path.suffix.lstrip(".").lower() or "mp4",
                            unit_type="frame",
                            unit_id=str(idx),
                            content=frame_text,
                            metadata={"timestamp": ts},
                            status="ok",
                        )
                    )
        finally:
            for fp, _ in frames:
                try:
                    fp.unlink(missing_ok=True)
                except Exception:
                    pass
            if frames:
                try:
                    frames[0][0].parent.rmdir()
                except Exception:
                    pass

        return rows
