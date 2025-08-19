# Copyright (c) 2025 takotime808

import io
import json
import pytest
from pathlib import Path

import pytest

from unifile.utils.utils import write_temp_file, json_dumps_safe, norm_ext


class LimitedBytesIO(io.BytesIO):
    """
    BytesIO that simulates chunked reads by honoring the size parameter in .read().
    (Regular BytesIO already does this, but this class makes the intent explicit.)
    """
    def read(self, n=-1):
        return super().read(n)


def test_write_temp_file_with_bytes_creates_file_and_preserves_content(tmp_path, monkeypatch):
    data = b"hello world"
    # Ensure mkstemp puts file in system temp; we still assert existence & suffix
    path = write_temp_file(data, suffix="txt")
    try:
        assert path.exists()
        assert path.suffix == ".txt"
        assert path.read_bytes() == data
    finally:
        # cleanup
        if path.exists():
            path.unlink(missing_ok=True)


def test_write_temp_file_with_stream_reads_in_chunks_and_preserves_content(tmp_path):
    # > 8192 bytes to ensure loop iterates multiple times
    payload = (b"ABC123-" * 4000)  # 7*4000 = 28,000 bytes
    stream = LimitedBytesIO(payload)

    path = write_temp_file(stream, suffix=".bin")
    try:
        assert path.exists()
        assert path.suffix == ".bin"
        out = path.read_bytes()
        assert out == payload
    finally:
        if path.exists():
            path.unlink(missing_ok=True)


def test_json_dumps_safe_serializable_object_round_trips():
    obj = {"a": [1, 2], "b": {"c": "x"}}
    s = json_dumps_safe(obj)
    # Should be valid JSON and round-trip equal
    assert isinstance(s, str)
    assert json.loads(s) == obj


def test_json_dumps_safe_non_serializable_returns_json_string_of_str_repr():
    class NotJSONable:
        pass

    val = NotJSONable()
    s = json_dumps_safe(val)
    # Should be a JSON-encoded string (quoted); json.loads should give a Python str
    parsed = json.loads(s)
    assert isinstance(parsed, str)
    # It should contain the __str__ / __repr__ of the object (memory address not asserted exactly)
    assert parsed  # non-empty


def test_json_dumps_safe_circular_reference_returns_string():
    l = []
    l.append(l)  # circular
    s = json_dumps_safe(l)
    parsed = json.loads(s)
    assert isinstance(parsed, str)
    assert parsed  # non-empty string


@pytest.mark.parametrize(
    "value,expected",
    [
        ("file.TXT", "txt"),
        ("archive.tar.gz", "gz"),
        ("noext", ""),
        (Path("Dir/another.PDF"), "pdf"),
        (".env", ""),          # dotfile -> pathlib treats as no suffix
        ("weird.name.", ""),   # trailing dot => no suffix
    ],
)
def test_norm_ext_various_cases(value, expected):
    assert norm_ext(value) == expected