import zipfile
from pathlib import Path

from unifile.extractors.archive_extractor import ArchiveExtractor
import unifile.pipeline as pipeline


def _build_nested_zip(path: Path):
    inner_txt = path.parent / "inner.txt"
    inner_txt.write_text("hi")
    inner_zip = path.parent / "inner.zip"
    with zipfile.ZipFile(inner_zip, "w") as z:
        z.write(inner_txt, "inner.txt")
    with zipfile.ZipFile(path, "w") as z:
        z.write(inner_zip, "inner.zip")


def test_archive_depth_limit(tmp_path, monkeypatch):
    outer = tmp_path / "outer.zip"
    _build_nested_zip(outer)
    monkeypatch.setenv("UNIFILE_ARCHIVE_MAX_DEPTH", "1")
    monkeypatch.setenv("UNIFILE_ARCHIVE_DEPTH", "0")
    pipeline.REGISTRY["zip"] = lambda: ArchiveExtractor()
    pipeline.SUPPORTED_EXTENSIONS.append("zip")
    ext = ArchiveExtractor()
    rows = ext.extract(outer)
    assert rows and rows[0].metadata.get("warning") == "max_depth_exceeded"
