import asyncio
from pathlib import Path
import pandas as pd

import unifile.pipeline as pipeline
from tests.integration.utils_build_samples import build_txt


def test_async_extract_paths(tmp_path):
    p1 = tmp_path / "a.txt"
    p2 = tmp_path / "b.txt"
    build_txt(p1)
    build_txt(p2)

    dfs = asyncio.run(pipeline.extract_paths([p1, p2]))
    assert isinstance(dfs, list) and len(dfs) == 2
    assert set(df.iloc[0]["source_name"] for df in dfs) == {"a.txt", "b.txt"}
