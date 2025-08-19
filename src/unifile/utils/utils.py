# Copyright (c) 2025 takotime808

from __future__ import annotations

import os
import io
import json
import tempfile
from pathlib import Path
from typing import Optional, Tuple, Union

def write_temp_file(data: Union[bytes, io.BufferedReader, io.BytesIO], suffix: str) -> Path:
    """
    Persist in-memory bytes or a readable binary stream to a temporary file.

    The file is created via :func:`tempfile.mkstemp` using a `unifile_` prefix
    and the provided suffix (a leading dot is added automatically if missing).

    Parameters
    ----------
    data
        Either raw bytes/bytearray or a binary, file-like object that implements
        ``read(size: int) -> bytes``. The stream is read in chunks until EOF.
    suffix
        Desired file suffix/extension. May be provided with or without the
        leading dot (e.g., ``"txt"`` or ``".txt"``).

    Returns
    -------
    pathlib.Path
        Path to the newly created temporary file containing the provided data.

    Notes
    -----
    - The caller is responsible for deleting the returned file when no longer
      needed.
    - Streams are read in 8 KiB chunks, which works for any binary-like object
      with a ``read()`` method (e.g., :class:`io.BytesIO`, open file handles,
      HTTP response streams, etc.).

    Examples
    --------
    >>> from io import BytesIO
    >>> p = write_temp_file(b"hello", "txt")
    >>> p.suffix
    '.txt'
    >>> p.read_text()
    'hello'
    >>> p.unlink()  # cleanup

    >>> s = BytesIO(b"chunked")
    >>> p = write_temp_file(s, ".bin")
    >>> p.read_bytes()
    b'chunked'
    >>> p.unlink()
    """
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    fd, tmp = tempfile.mkstemp(suffix=suffix, prefix="unifile_")
    os.close(fd)
    path = Path(tmp)
    if isinstance(data, (bytes, bytearray)):
        path.write_bytes(data)
    else:
        # assume file-like
        with open(path, "wb") as f:
            chunk = data.read(8192)
            while chunk:
                f.write(chunk)
                chunk = data.read(8192)
    return path

def json_dumps_safe(obj) -> str:
    """
    Serialize an object to JSON, falling back to the object's string
    representation when default JSON encoding fails.

    Parameters
    ----------
    obj
        Any Python object.

    Returns
    -------
    str
        A JSON string. If ``obj`` is JSON-serializable, the result is the usual
        JSON encoding. Otherwise, returns a JSON-encoded string of ``str(obj)``.

    Examples
    --------
    >>> json_dumps_safe({"a": 1})
    '{"a": 1}'

    >>> json_dumps_safe(object())[:1] == '"'
    True

    >>> l = []; l.append(l)  # circular structure
    >>> isinstance(json.loads(json_dumps_safe(l)), str)
    True
    """
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return json.dumps(str(obj), ensure_ascii=False)

def norm_ext(p: Union[str, Path]) -> str:
    """
    Normalize a file's extension to lowercase without the leading dot.

    Parameters
    ----------
    p
        A path-like string or :class:`pathlib.Path`.

    Returns
    -------
    str
        The lowercase extension **without** the leading dot. If the input
        has no extension, returns an empty string. For dotfiles (e.g. ``.env``),
        this returns the text after the dot (``"env"``), consistent with
        :attr:`pathlib.Path.suffix`.

    Examples
    --------
    >>> norm_ext("file.TXT")
    'txt'
    >>> norm_ext("archive.tar.gz")
    'gz'
    >>> norm_ext("noext")
    ''
    >>> norm_ext(".env")
    'env'
    """
    return Path(p).suffix.lower().lstrip(".")
