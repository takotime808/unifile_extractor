# Copyright (c) 2025 takotime808
import pytest

import unifile.pipeline as pipeline

@pytest.mark.skipif("wav" not in pipeline.SUPPORTED_EXTENSIONS, reason="media extras not installed")
def test_audio_extractor_end_to_end_with_mocks(tmp_path, monkeypatch):
    from unifile.extractors import audio_extractor as ae
    # Mock ASR and probe
    monkeypatch.setattr(ae._ASR, "transcribe", staticmethod(lambda p: ("audio text", {"segments":[{"start":0.0,"end":0.5,"text":"seg"}]})))
    monkeypatch.setattr(ae, "_probe_media", lambda p: {"format":{"format_name":"wav","duration":"2.0"}})

    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")  # dummy header

    df = pipeline.extract_to_table(wav, asr_model="base", asr_device="cpu")
    assert len(df) == 1
    row = df.iloc[0]
    assert row["file_type"] == "wav"
    assert row["unit_type"] == "audio"
    assert "segments" in row["metadata"]
    assert row["metadata"]["probe"]["format"] == "wav"

@pytest.mark.skipif("mp4" not in pipeline.SUPPORTED_EXTENSIONS, reason="media extras not installed")
def test_video_extractor_end_to_end_with_mocks(tmp_path, monkeypatch):
    from unifile.extractors import video_extractor as ve
    # Monkeypatch helper to avoid ffmpeg, return a temp wav path
    dummy_wav = tmp_path / "t.wav"
    dummy_wav.write_bytes(b"RIFF")
    monkeypatch.setattr(ve, "_ffmpeg_audio", lambda p: dummy_wav)
    # Mock ASR and probe
    from unifile.extractors.audio_extractor import _ASR
    monkeypatch.setattr(_ASR, "transcribe", staticmethod(lambda p: ("video transcript", {"segments":[{"start":0.0,"end":1.0,"text":"v"}]})))
    monkeypatch.setattr(ve, "_probe_video", lambda p: {"format":{"format_name":"mp4","duration":"3.0"},"streams":[{"codec_type":"video"},{"codec_type":"audio"}]})

    mp4 = tmp_path / "v.mp4"
    mp4.write_bytes(b"")
    df = pipeline.extract_to_table(mp4, asr_model="small", asr_device="cpu")
    assert len(df) == 1
    row = df.iloc[0]
    assert row["file_type"] == "mp4"
    assert row["unit_type"] == "video"
    assert "segments" in row["metadata"]
    assert row["metadata"]["probe"]["format"] == "mp4"
    assert isinstance(row["metadata"]["probe"]["video_streams"], list)
    assert isinstance(row["metadata"]["probe"]["audio_streams"], list)
