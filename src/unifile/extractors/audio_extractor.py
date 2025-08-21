# Copyright (c) 2025 takotime808

"""
Audio --> transcript extractor (optional).

Backends (auto-selected at runtime):
1) faster-whisper  (fastest, GPU-friendly if available)
2) openai-whisper  (CPU works; slower)

Requirements (install optional extra):
    pip install ".[media]"

Binary:
    FFmpeg is recommended (for robust decoding across formats).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple, Dict, Any
import tempfile
import subprocess
import json

from unifile.extractors.base import (
    BaseExtractor,
    make_row,
    Row,
)


def _probe_media(path: Path) -> Dict[str, Any]:
    """Return a small info dict using ffprobe if available, else {}."""
    try:
        # Minimal, fast probe
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            stderr=subprocess.STDOUT,
        )
        return json.loads(out.decode("utf-8", errors="replace"))
    except Exception:
        return {}


def _ensure_wav(input_path: Path) -> Path:
    """
    Ensure we have a WAV file on disk. If input isn't .wav, convert with ffmpeg.
    Returns the path to a WAV (may be the original if already .wav).
    """
    if input_path.suffix.lower() == ".wav":
        return input_path

    wav_path = Path(tempfile.mkstemp(prefix="unifile_audio_", suffix=".wav")[1])
    try:
        subprocess.check_call([
            "ffmpeg", "-y", "-i", str(input_path),
            "-ac", "1", "-ar", "16000",  # mono 16k for ASR
            str(wav_path)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return wav_path
    except FileNotFoundError:
        # ffmpeg missing; fall back to original path (backend may still decode)
        return input_path


class _ASR:
    """
    Lazy ASR model loader that prefers faster-whisper; falls back to openai-whisper.

    Environment overrides:
        UNIFILE_ASR_MODEL   (default: "small")
        UNIFILE_ASR_DEVICE  (e.g., "cuda" or "cpu"; backend-dependent)
        UNIFILE_ASR_COMPUTE_TYPE (faster-whisper only, e.g., "float16","int8_float16")
    """
    _initialized = False
    _use_fw = False
    _model = None

    @classmethod
    def _init(cls):
        if cls._initialized:
            return
        import os

        model_name = os.getenv("UNIFILE_ASR_MODEL", "small")
        device = os.getenv("UNIFILE_ASR_DEVICE", None)
        compute_type = os.getenv("UNIFILE_ASR_COMPUTE_TYPE", "default")

        try:
            from faster_whisper import WhisperModel
            kwargs = {}
            if device:
                kwargs["device"] = device
            if compute_type and compute_type != "default":
                kwargs["compute_type"] = compute_type
            cls._model = WhisperModel(model_name, **kwargs)
            cls._use_fw = True
        except Exception:
            import whisper  # openai-whisper
            if device:
                cls._model = whisper.load_model(model_name, device=device)
            else:
                cls._model = whisper.load_model(model_name)
            cls._use_fw = False

        cls._initialized = True

    @classmethod
    def transcribe(cls, audio_path: Path) -> Tuple[str, Dict[str, Any]]:
        """
        Return (text, meta). Meta includes segments (start,end,text) when available.
        """
        cls._init()
        segments_meta = []
        if cls._use_fw:
            # faster-whisper stream of segments
            try:
                segments, info = cls._model.transcribe(str(audio_path))
            except TypeError:
                # older API returns generator + info
                segments_iter, info = cls._model.transcribe(str(audio_path), vad_filter=False)
                segments = list(segments_iter)
            text_parts = []
            for s in segments:
                text_parts.append(s.text or "")
                segments_meta.append({"start": float(s.start or 0), "end": float(s.end or 0), "text": s.text or ""})
            return " ".join(t.strip() for t in text_parts).strip(), {"segments": segments_meta}
        else:
            # openai-whisper returns dict with segments
            import whisper
            result = cls._model.transcribe(str(audio_path))
            text = (result.get("text") or "").strip()
            for s in result.get("segments", []) or []:
                segments_meta.append({"start": float(s.get("start", 0)), "end": float(s.get("end", 0)), "text": s.get("text", "")})
            return text, {"segments": segments_meta}


class AudioExtractor(BaseExtractor):
    """
    Audio --> transcript.

    Supported extensions
    --------------------
    wav, mp3, m4a, flac, ogg, webm, aac

    Output Row
    ----------
    - file_type: normalized (e.g., "mp3")
    - unit_type: "audio"
    - unit_id:   "0"
    - content:   transcription text
    - metadata:  {"segments":[...], "probe":{...}} (best-effort)
    """

    supported_extensions = ["wav", "mp3", "m4a", "flac", "ogg", "webm", "aac"]

    def _extract(self, path: Path) -> List[Row]:
        wav = _ensure_wav(path)
        text, meta = _ASR.transcribe(wav)
        if wav != path:
            try:
                wav.unlink(missing_ok=True)
            except Exception:
                pass
        # Best-effort probe metadata (duration/codec)
        probe = _probe_media(path)
        meta["probe"] = {"format": (probe.get("format") or {}).get("format_name"), "duration": (probe.get("format") or {}).get("duration")}
        return [
            make_row(
                path=path,
                file_type=path.suffix.lstrip(".").lower() or "wav",
                unit_type="audio",
                unit_id="0",
                content=text or "",
                metadata=meta,
                status="ok",
            )
        ]
