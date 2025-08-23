import pandas as pd
from cli_unifile import cli
from unifile.processing import schema as schema_mod


def test_cli_validate(tmp_path):
    cols = schema_mod.expected_columns()
    df = pd.DataFrame([{c: None for c in cols}])
    path = tmp_path / "table.ndjson"
    df.to_json(path, orient="records", lines=True)
    rc = cli.main(["validate", str(path)])
    assert rc == 0

    bad = tmp_path / "bad.ndjson"
    pd.DataFrame([{"foo": 1}]).to_json(bad, orient="records", lines=True)
    rc2 = cli.main(["validate", str(bad)])
    assert rc2 == 1
