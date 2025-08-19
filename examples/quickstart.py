# Copyright (c) 2025 takotime808

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
from unifile import extract_to_table, SUPPORTED_EXTENSIONS

def main():
    ap = argparse.ArgumentParser(description="Unified text extraction -> standardized table")
    ap.add_argument("file", help="Path to the input file") 
    ap.add_argument("--out", help="Optional path to write CSV/Parquet of the standardized table") 
    args = ap.parse_args()

    df = extract_to_table(args.file)
    print(df.to_string(max_colwidth=80, max_rows=100))

    if args.out:
        out_path = Path(args.out)
        if out_path.suffix.lower() == ".parquet":
            df.to_parquet(out_path, index=False)
        else:
            df.to_csv(out_path, index=False)
        print(f"\nSaved standardized table -> {out_path}")

if __name__ == "__main__":
    main()
