"""Simple manifest and deduplication utilities."""

from __future__ import annotations

import hashlib
import json
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Set, Tuple


@dataclass
class Manifest:
    """Track processed files to avoid duplicates.

    Parameters
    ----------
    path:
        Location of the manifest JSON Lines file.
    """

    path: Path
    hashes: Set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    obj = json.loads(line)
                    h = obj.get("hash")
                    if h:
                        self.hashes.add(h)
                except Exception:
                    continue

    def _hash_file(self, file_path: Path) -> Tuple[str, int]:
        data = file_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        return digest, len(data)

    def check(self, file_path: Path) -> Tuple[bool, str, int]:
        """Return (is_duplicate, hash, size)."""
        h, size = self._hash_file(file_path)
        return h in self.hashes, h, size

    def record(self, file_path: Path, status: str) -> None:
        """Append an entry for ``file_path`` with ``status`` to the manifest."""
        h, size = self._hash_file(file_path)
        mime = mimetypes.guess_type(str(file_path))[0] or ""
        entry = {
            "path": str(file_path),
            "hash": h,
            "bytes": size,
            "mime": mime,
            "status": status,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        self.hashes.add(h)
