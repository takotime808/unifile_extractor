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
from PIL import Image
import pytesseract
import random
try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    np = None

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

    def __init__(self, frame_ocr: bool = False, frame_interval: int = 10, ocr_lang: str = "eng", ocr_langs: str | None = None, deterministic: bool = False):
        self.frame_ocr = frame_ocr
        self.frame_interval = frame_interval
        self.ocr_lang = ocr_lang
        self.ocr_langs = ocr_langs
        self.deterministic = deterministic

    def _ffmpeg_frames(self, path: Path) -> Tuple[List[Tuple[Path, float]], tempfile.TemporaryDirectory]:
        td = tempfile.TemporaryDirectory(prefix="unifile_frames_")
        pattern = Path(td.name) / "frame_%06d.png"
        subprocess.check_call([
            "ffmpeg", "-y", "-i", str(path),
            "-vf", f"fps=1/{max(self.frame_interval,1)}", str(pattern)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        frames = sorted(Path(td.name).glob("frame_*.png"))
        out: List[Tuple[Path, float]] = []
        for idx, fp in enumerate(frames):
            out.append((fp, idx * float(self.frame_interval)))
        return out, td

    def _ocr_frame(self, img_path: Path) -> Tuple[str, str]:
        with Image.open(str(img_path)) as img:
            if self.deterministic:
                random.seed(0)
                if np is not None:
                    try:
                        np.random.seed(0)
                    except Exception:
                        pass
                config = "--dpi 300"
            else:
                config = ""
            langs = (self.ocr_langs.split("+") if self.ocr_langs else [self.ocr_lang])
            used = self.ocr_lang
            for lang in langs:
                t = pytesseract.image_to_string(img, lang=lang, config=config) or ""
                if t.strip():
                    return t, lang
            return "", used

    def _extract(self, path: Path) -> List[Row]:
        rows: List[Row] = []
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

        if self.frame_ocr:
            try:
                frames, td = self._ffmpeg_frames(path)
                for idx, (fp, ts) in enumerate(frames):
                    txt, lang = self._ocr_frame(fp)
                    rows.append(
                        make_row(
                            path=path,
                            file_type=path.suffix.lstrip(".").lower() or "mp4",
                            unit_type="frame",
                            unit_id=str(idx),
                            content=txt,
                            metadata={"timestamp": ts, "lang": lang},
                            status="ok",
                        )
                    )
            finally:
                try:
                    td.cleanup()  # remove temp dir and frames
                except Exception:
                    pass

        return rows
