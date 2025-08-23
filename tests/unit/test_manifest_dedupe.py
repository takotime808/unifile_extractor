from unifile.pipeline import extract_to_table
from unifile.processing.manifest import Manifest


def test_manifest_dedupe(tmp_path, simple_txt):
    m = Manifest(tmp_path / "manifest.jsonl")
    df1 = extract_to_table(simple_txt, manifest=m)
    assert len(df1) == 1
    df2 = extract_to_table(simple_txt, manifest=m)
    assert df2.empty
    lines = (tmp_path / "manifest.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    assert '"duplicate"' in lines[1]
