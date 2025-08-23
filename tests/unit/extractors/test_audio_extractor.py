import wave
from pathlib import Path

import unifile.extractors.audio_extractor as mod


def _make_wav(path: Path):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)


def test_asr_chunking(monkeypatch, tmp_path):
    wav = tmp_path / "in.wav"
    _make_wav(wav)

    calls = []

    class DummyModel:
        def transcribe(self, path):
            idx = len(calls)
            calls.append(Path(path))
            class S:
                start = 0
                end = 1
                text = f"c{idx}"

            return [S()], {}

    monkeypatch.setattr(mod._ASR, "_initialized", True)
    monkeypatch.setattr(mod._ASR, "_use_fw", True)
    monkeypatch.setattr(mod._ASR, "_model", DummyModel())

    def fake_check_call(cmd, stdout=None, stderr=None):
        pattern = cmd[-1]
        Path(pattern.replace("%03d", "000")).write_bytes(b"")
        Path(pattern.replace("%03d", "001")).write_bytes(b"")

    monkeypatch.setattr(mod.subprocess, "check_call", fake_check_call)

    text, meta = mod._ASR.transcribe(wav, chunk_seconds=1.0)
    assert len(calls) == 2
    assert meta["segments"][1]["start"] >= 1.0
