# Copyright (c) 2025 takotime808

import pytest
from pathlib import Path
from PIL import Image, ImageDraw

import unifile.extractors.img_extractor as mod
from unifile.extractors.img_extractor import ImageExtractor

def _build_image(path: Path):
    img = Image.new("RGB", (200, 80), (255,255,255))
    d = ImageDraw.Draw(img)
    d.text((10, 30), "HELLO", fill=(0,0,0))
    img.save(path)

def test_image_extractor_uses_ocr(tmp_path, monkeypatch):
    p = tmp_path / "sample.png"
    _build_image(p)

    # Mock pytesseract to avoid depending on tesseract binary in CI
    def fake_ocr(img, lang="eng", config=""):
        return "HELLO MOCK"
    monkeypatch.setattr(mod, "pytesseract", type("X", (), {"image_to_string": staticmethod(fake_ocr)}))

    ext = ImageExtractor()
    rows = ext.extract(p)
    assert rows and rows[0].unit_type == "image"
    assert "HELLO" in rows[0].content
    assert rows[0].metadata["width"] == 200
    assert rows[0].metadata["height"] == 80


def test_image_extractor_deterministic_multilang(tmp_path, monkeypatch):
    p = tmp_path / "sample.png"
    _build_image(p)

    calls = []

    def fake_ocr(img, lang="eng", config=""):
        calls.append({"lang": lang, "config": config})
        return "HELLO"

    monkeypatch.setattr(mod, "pytesseract", type("X", (), {"image_to_string": staticmethod(fake_ocr)}))
    monkeypatch.delenv("UNIFILE_OCR_LANGS", raising=False)
    monkeypatch.delenv("UNIFILE_DETERMINISTIC", raising=False)
    ext = ImageExtractor(ocr_langs="eng+spa", deterministic=True)
    ext.extract(p)
    assert calls[0]["lang"] == "eng+spa"
    assert "--dpi 300" in calls[0]["config"]


@pytest.mark.skipif(not mod._HAS_HEIF, reason="pillow-heif is not installed")
def test_image_extractor_supports_heic(tmp_path, monkeypatch):
    p = tmp_path / "sample.heic"
    _build_image(p)

    def fake_ocr(img, lang="eng"):
        return "HELLO HEIC"

    monkeypatch.setattr(mod, "pytesseract", type("X", (), {
        "image_to_string": staticmethod(fake_ocr)
    }))

    ext = ImageExtractor()
    rows = ext.extract(p)
    assert rows and rows[0].file_type == "heic"
    assert "HELLO" in rows[0].content
