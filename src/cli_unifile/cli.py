# Copyright (c) 2025 takotime808

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional
import pandas as pd
import tomllib

from unifile import version, SUPPORTED_EXTENSIONS
from unifile.pipeline import extract_to_table, list_plugins
from unifile.processing.manifest import Manifest
from unifile.processing import schema as schema_mod
# from unifile.utils.utils import norm_ext

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


def _download(url: str, out: Path) -> Path:
    if requests is None:
        raise RuntimeError("requests is required to download URLs. Please install 'requests'.")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    out.write_bytes(resp.content)
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="unifile",
        description="Unified text extraction CLI: ingest docs/images/spreadsheets and emit a standardized table.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {version()}")
    p.add_argument("--config", help="TOML config file with default options.")

    sub = p.add_subparsers(dest="cmd", required=True)

    # extract
    ep = sub.add_parser("extract", help="Extract from a file path or URL into a standardized table.")
    ep.add_argument("src", help="Path to a local file OR a URL (http/https).")
    ep.add_argument(
        "--out",
        help="Optional output file for the standardized table. "
             "Extensions: .csv, .parquet, .jsonl. Defaults to printing to stdout.",
    )
    ep.add_argument("--to", choices=["parquet", "arrow", "ndjson", "sqlite", "duckdb"],
                    help="Output format when --out is provided.")
    ep.add_argument("--manifest", help="Path to a manifest.jsonl for dedupe", default=None)
    ep.add_argument("--ocr-lang", default=None, help="OCR language for images and OCR fallback (default: eng).")
    ep.add_argument("--no-ocr", action=argparse.BooleanOptionalAction, default=None,
                    help="Disable OCR fallback for PDFs (vector text only).")
    ep.add_argument("--max-rows", type=int, default=None, help="Limit number of rows printed to stdout.")
    ep.add_argument("--max-colwidth", type=int, default=None, help="Max col width when printing to stdout.")

    # list types
    lp = sub.add_parser("list-types", help="List supported file extensions.")
    lp.add_argument("--one-per-line", action="store_true", help="Print one extension per line.")

    sub.add_parser("plugins", help="List available extractor plugins.")

    vp = sub.add_parser("validate", help="Validate a table against schema_v1.json")
    vp.add_argument("src", help="Path to table file (jsonl/parquet/ndjson/sqlite/duckdb)")

    return p


def _save_df(df: pd.DataFrame, out: Path, fmt: Optional[str] = None) -> None:
    """Save ``df`` to ``out`` using the requested format."""
    fmt = (fmt or out.suffix.lower().lstrip(".")).lower()
    if fmt == "csv":
        df.to_csv(out, index=False)
    elif fmt == "parquet":
        df.to_parquet(out, index=False)
    elif fmt == "arrow":
        df.to_feather(out)
    elif fmt in {"jsonl", "ndjson"}:
        out.write_text("", encoding="utf-8")
        chunk = 1000
        with out.open("a", encoding="utf-8") as fh:
            for i in range(0, len(df), chunk):
                fh.write(df.iloc[i:i+chunk].to_json(orient="records", lines=True, force_ascii=False))
                fh.write("\n")
    elif fmt == "sqlite":
        import sqlite3
        import json

        df2 = df.copy()
        for c in df2.columns:
            df2[c] = df2[c].apply(lambda v: json.dumps(v) if isinstance(v, (dict, list)) else v)
        conn = sqlite3.connect(out)
        df2.to_sql("rows", conn, if_exists="append", index=False, chunksize=1000)
        conn.close()
    elif fmt == "duckdb":
        import duckdb
        import json

        con = duckdb.connect(str(out))
        con.execute("CREATE TABLE IF NOT EXISTS rows AS SELECT * FROM df LIMIT 0")
        for i in range(0, len(df), 1000):
            chunk_df = df.iloc[i:i+1000].copy()
            for c in chunk_df.columns:
                chunk_df[c] = chunk_df[c].apply(lambda v: json.dumps(v) if isinstance(v, (dict, list)) else v)
            con.register("chunk", chunk_df)
            con.execute("INSERT INTO rows SELECT * FROM chunk")
        con.close()
    else:
        raise ValueError(
            f"Unsupported output format '{fmt}'. Use csv/parquet/arrow/ndjson/sqlite/duckdb"
        )


def _print_df(df: pd.DataFrame, max_rows: Optional[int], max_colwidth: int) -> None:
    with pd.option_context("display.max_rows", max_rows or 20, "display.max_colwidth", max_colwidth):
        print(df.to_string())


def _read_df(path: Path) -> pd.DataFrame:
    """Load a table from ``path`` into a DataFrame based on extension."""
    sfx = path.suffix.lower()
    if sfx in {".jsonl", ".ndjson"}:
        return pd.read_json(path, lines=True)
    if sfx == ".parquet":
        return pd.read_parquet(path)
    if sfx == ".arrow":
        return pd.read_feather(path)
    if sfx == ".sqlite":
        import sqlite3

        conn = sqlite3.connect(path)
        df = pd.read_sql("SELECT * FROM rows", conn)
        conn.close()
        return df
    if sfx == ".duckdb":
        import duckdb

        con = duckdb.connect(str(path))
        df = con.execute("SELECT * FROM rows").to_df()
        con.close()
        return df
    raise ValueError(f"Unsupported format: {path}")


def main(argv: Optional[list[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(argv)

    cfg = {}
    if args.config:
        cfg = tomllib.loads(Path(args.config).read_text())

    if args.cmd == "plugins":
        for name in list_plugins():
            print(name)
        return 0

    if args.cmd == "list-types":
        if args.one_per_line:
            for ext in SUPPORTED_EXTENSIONS:
                print(ext)
        else:
            print(", ".join(SUPPORTED_EXTENSIONS))
        return 0

    if args.cmd == "extract":
        src = args.src
        tmp_download: Optional[Path] = None

        # Detect URL vs file
        if src.startswith("http://") or src.startswith("https://"):
            # derive filename from URL or fallback
            from urllib.parse import urlparse
            name = Path(urlparse(src).path).name or "downloaded.bin"
            tmp_download = Path.cwd() / f"unifile_download_{name}"
            _download(src, tmp_download)
            path = tmp_download
        else:
            path = Path(src)
            if not path.exists():
                print(f"error: file not found: {path}", file=sys.stderr)
                return 2

        # Merge config and env variables for runtime options
        cfg_extract = cfg.get("extract", {}) if isinstance(cfg, dict) else {}
        ocr_lang = (
            args.ocr_lang
            or os.getenv("UNIFILE_OCR_LANG")
            or cfg_extract.get("ocr_lang")
            or "eng"
        )
        if args.no_ocr is not None:
            no_ocr = args.no_ocr
        else:
            env_no_ocr = os.getenv("UNIFILE_DISABLE_PDF_OCR")
            if env_no_ocr not in (None, ""):
                try:
                    no_ocr = bool(int(env_no_ocr))
                except ValueError:
                    no_ocr = bool(env_no_ocr)
            else:
                no_ocr = cfg_extract.get("no_ocr", False)
        out = args.out or cfg_extract.get("out")
        max_rows = args.max_rows if args.max_rows is not None else cfg_extract.get("max_rows")
        max_colwidth = args.max_colwidth if args.max_colwidth is not None else cfg_extract.get("max_colwidth", 120)

        manifest = Manifest(Path(args.manifest)) if args.manifest else None
        kwargs = dict(ocr_lang=ocr_lang, no_ocr=no_ocr)
        if manifest is not None:
            kwargs["manifest"] = manifest
        df = extract_to_table(path, **kwargs)

        if out:
            out_path = Path(out)
            _save_df(df, out_path, fmt=args.to)
            print(f"Saved standardized table -> {out_path}")
        else:
            _print_df(df, max_rows=max_rows, max_colwidth=max_colwidth)

        if tmp_download and tmp_download.exists():
            try:
                tmp_download.unlink()
            except Exception:
                pass

        return 0

    if args.cmd == "validate":
        path = Path(args.src)
        df = _read_df(path)
        if schema_mod.validate_columns(df.columns):
            return 0
        print("schema mismatch", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())