# Copyright (c) 2025 takotime808

from __future__ import annotations

from pathlib import Path
from typing import List
import os
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
    """Extractor for archive files (ZIP/TAR and variants).

    This extractor unpacks supported archives into a temporary
    directory, then recursively runs the extraction pipeline on each
    contained file. Rows emitted from child extractors are enriched with
    an ``archive_member`` metadata field indicating the relative path of
    the file within the archive.

    Supported extensions
    --------------------
    zip, tar, gz, tgz, bz2, tbz, xz
    """
    supported_extensions = ["zip", "tar", "gz", "tgz", "bz2", "tbz", "xz"]

    def _extract(self, path: Path) -> List[Row]:
        """Extract and process the contents of an archive.

        The archive is unpacked into a temporary directory using either
        ``zipfile`` (for `.zip`) or ``tarfile`` (for `.tar` and compressed
        variants). Each extracted file is then passed to the pipeline
        (`extract_to_table`) with the appropriate extractor. If supported
        files are found, their rows are returned with additional metadata
        indicating their archive path. If no supported files are found,
        a single placeholder row is emitted.

        Args:
            path (Path): Path to the archive file.

        Returns:
            List[Row]: A list of rows aggregated from all extracted files.
                Each row includes:
                - source type: Derived from inner file type
                - level/unit_type/unit_id: As reported by the delegated extractor
                - text: Content extracted by the delegated extractor
                - metadata: Original metadata plus ``archive_member`` path
        """
        depth = int(os.getenv("UNIFILE_ARCHIVE_DEPTH", "0"))
        max_depth = int(os.getenv("UNIFILE_ARCHIVE_MAX_DEPTH", "3"))
        if depth >= max_depth:
            return [
                make_row(
                    path,
                    path.suffix.lstrip(".").lower(),
                    "file",
                    "members",
                    "",
                    {"warning": "max_depth_exceeded"},
                    status="error",
                )
            ]

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
                os.environ["UNIFILE_ARCHIVE_DEPTH"] = str(depth + 1)
                df = extract_to_table(p)
                os.environ["UNIFILE_ARCHIVE_DEPTH"] = str(depth)
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
