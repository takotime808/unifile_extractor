"""Batch a directory of files and write them to a single Parquet file."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import pandas as pd

from unifile.pipeline import extract_paths


async def batch_directory_to_parquet(src_dir: str, out_path: str) -> None:
    """Extract all files under ``src_dir`` and write the combined table to ``out_path``.

    Parameters
    ----------
    src_dir:
        Directory containing input files.
    out_path:
        Destination Parquet file path.
    """
    paths = [p for p in Path(src_dir).iterdir() if p.is_file()]
    dfs = await extract_paths(paths)
    pd.concat(dfs, ignore_index=True).to_parquet(out_path, index=False)


def main() -> None:
    """CLI entry point for batching a directory to Parquet."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src_dir", help="Directory of files to extract")
    ap.add_argument("out", help="Output Parquet file")
    args = ap.parse_args()
    asyncio.run(batch_directory_to_parquet(args.src_dir, args.out))


if __name__ == "__main__":
    main()
