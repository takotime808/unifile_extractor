import pytest
from pathlib import Path
from PIL import Image, ImageDraw

import unifile.extractors.video_extractor as mod
from unifile.extractors.video_extractor import VideoExtractor


def _mk_img(path: Path, text: str):
    img = Image.new("RGB", (20, 20), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((2, 5), text, fill=(0, 0, 0))
    img.save(path)


def test_video_extractor_keyframes(monkeypatch, tmp_path):
    video = tmp_path / "vid.mp4"
    video.write_bytes(b"fake")

    def fake_ffmpeg_audio(path):
        wav = tmp_path / "a.wav"
        wav.write_bytes(b"data")
        return wav

    monkeypatch.setattr(mod, "_ffmpeg_audio", staticmethod(fake_ffmpeg_audio))
    monkeypatch.setattr(mod._ASR, "transcribe", staticmethod(lambda p: ("AUDIO", {})))

    frame1, frame2 = tmp_path / "f1.png", tmp_path / "f2.png"
    _mk_img(frame1, "A")
    _mk_img(frame2, "B")

    def fake_ffmpeg_frames(path, interval):
        return [(frame1, 0.0), (frame2, 5.0)]

    monkeypatch.setattr(mod, "_ffmpeg_frames", staticmethod(fake_ffmpeg_frames))

    calls = []

    def fake_ocr(img, lang="eng", config=""):
        calls.append({"lang": lang, "config": config})
        return "TXT"

    monkeypatch.setattr(mod, "pytesseract", type("T", (), {"image_to_string": staticmethod(fake_ocr)}))

    vx = VideoExtractor(frame_interval=5.0, ocr_langs="eng", deterministic=True)
    rows = vx.extract(video)
    assert rows[0].unit_type == "video"
    frames = [r for r in rows if r.unit_type == "frame"]
    assert len(frames) == 2
    assert frames[0].metadata["timestamp"] == 0.0
    assert "--dpi 300" in calls[0]["config"]
