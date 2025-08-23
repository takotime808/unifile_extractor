# Copyright (c) 2025 takotime808
import os
import pytest
from pathlib import Path

import unifile.pipeline as pipeline
from unifile.extractors.base import make_row

class CapturingPdf:
    def __init__(self, ocr_if_empty=True, ocr_lang="eng"):
        self.ocr_if_empty = ocr_if_empty
        self.ocr_lang = ocr_lang
    def extract(self, path: Path):
        return [make_row(path, "pdf", "page", "0", "PDF", {"ocr_lang": self.ocr_lang, "ocr_if_empty": self.ocr_if_empty})]

class CapturingImage:
    def __init__(self, ocr_lang="eng"):
        self.ocr_lang = ocr_lang
    def extract(self, path: Path):
        return [make_row(path, "png", "image", "0", "IMG", {"ocr_lang": self.ocr_lang})]

def test_pdf_and_image_constructor_receive_runtime_options(tmp_path, monkeypatch):
    # stub classes into pipeline namespace
    monkeypatch.setattr(pipeline, "PdfExtractor", CapturingPdf)
    monkeypatch.setattr(pipeline, "ImageExtractor", CapturingImage)

    # Force registry to include relevant keys mapped to base registry
    # (pipeline._make_extractor_for_ext uses the names above)
    f_pdf = tmp_path / "a.pdf"
    f_pdf.write_bytes(b"%PDF-1.4")

    f_png = tmp_path / "a.png"
    f_png.write_bytes(b"fakepng")

    # provide options to extract_to_table
    df_pdf = pipeline.extract_to_table(f_pdf, ocr_lang="deu", no_ocr=True)
    df_img = pipeline.extract_to_table(f_png, ocr_lang="spa")

    r_pdf = df_pdf.iloc[0]
    r_img = df_img.iloc[0]

    assert r_pdf["file_type"] == "pdf"
    assert r_pdf["metadata"]["ocr_lang"] == "deu"
    assert r_pdf["metadata"]["ocr_if_empty"] is False  # because no_ocr=True disables
    assert r_img["metadata"]["ocr_lang"] == "spa"


def test_asr_env_vars_set_when_options_passed(tmp_path, monkeypatch):
    # Use a .wav to avoid ffmpeg path; the audio extractor will call _ASR.transcribe.
    from unifile.extractors import audio_extractor as ae
    # Make sure import exists; otherwise skip
    if ae is None:
        pytest.skip("audio_extractor not available")
    wav = tmp_path / "empty.wav"
    wav.write_bytes(b"RIFF0000")  # dummy

    # Mock transcribe to avoid heavy models
    def fake_transcribe(path):
        return "hello world", {"segments": [{"start":0.0,"end":1.0,"text":"hello world"}]}
    monkeypatch.setattr(ae._ASR, "transcribe", staticmethod(fake_transcribe))

    # Mock probe to stable dict
    monkeypatch.setattr(ae, "_probe_media", lambda p: {"format":{"format_name":"wav","duration":"1.0"}})

    # ensure registry maps wav to AudioExtractor
    import unifile.pipeline as pl
    if "wav" not in pl.SUPPORTED_EXTENSIONS:
        pytest.skip("media extras not enabled")

    # Call with ASR options
    pl.extract_to_table(wav, asr_model="small", asr_device="cpu", asr_compute_type="int8_float16")

    assert os.environ.get("UNIFILE_WHISPER_MODEL") == "small"
    assert os.environ.get("UNIFILE_ASR_DEVICE") == "cpu"
    assert os.environ.get("UNIFILE_ASR_COMPUTE_TYPE") == "int8_float16"
