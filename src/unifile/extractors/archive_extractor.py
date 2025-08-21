# Copyright (c) 2025 takotime808

from __future__ import annotations

from pathlib import Path
from typing import List
import tempfile, shutil, tarfile, zipfile

from unifile.extractors.base import (
    BaseExtractor,
    make_row,
    Row,
)
from unifile.pipeline import (
    extract_to_table,
    detect_extractor,
)


class ArchiveExtractor(BaseExtractor):
    """ZIP/TAR --> recursively extract members and run the pipeline on each."""
    supported_extensions = ["zip", "tar", "gz", "tgz", "bz2", "tbz", "xz"]

    def _extract(self, path: Path) -> List[Row]:
        out: List[Row] = []
        work = Path(tempfile.mkdtemp(prefix="unifile_unzip_"))
        try:
            # Unpack
            if path.suffix.lower() == ".zip":
                with zipfile.ZipFile(path) as z:
                    z.extractall(work)
            else:
                with tarfile.open(path) as t:
                    t.extractall(work)

            # Walk extracted files and delegate to pipeline
            for p in work.rglob("*"):
                if not p.is_file():
                    continue
                ext = detect_extractor(p)
                if not ext:
                    continue
                df = extract_to_table(p)
                for _, r in df.iterrows():
                    meta = dict(r["metadata"] or {})
                    meta["archive_member"] = str(p.relative_to(work))
                    out.append(Row(
                        source_path=r["source_path"], source_name=r["source_name"], file_type=r["file_type"],
                        unit_type=r["unit_type"], unit_id=r["unit_id"], content=r["content"],
                        char_count=r["char_count"], metadata=meta, status=r["status"], error=r["error"]
                    ))
            if not out:
                out.append(make_row(path, path.suffix.lstrip('.').lower(), "file", "members", "", {"note": "no supported files found"}))
            return out
        finally:
            shutil.rmtree(work, ignore_errors=True)
