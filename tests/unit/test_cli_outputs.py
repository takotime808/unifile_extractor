import pandas as pd
from cli_unifile import cli
import sqlite3


def test_cli_extract_ndjson(tmp_path, simple_txt):
    out = tmp_path / "out.ndjson"
    rc = cli.main(["extract", str(simple_txt), "--out", str(out), "--to", "ndjson"])
    assert rc == 0
    assert out.exists()
    df = pd.read_json(out, lines=True)
    assert not df.empty


def test_cli_extract_sqlite(tmp_path, simple_txt):
    out = tmp_path / "out.sqlite"
    rc = cli.main(["extract", str(simple_txt), "--out", str(out), "--to", "sqlite"])
    assert rc == 0
    conn = sqlite3.connect(out)
    cnt = conn.execute("SELECT COUNT(*) FROM rows").fetchone()[0]
    conn.close()
    assert cnt > 0
