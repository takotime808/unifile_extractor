# Copyright (c) 2025 takotime808

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional
import pandas as pd

from unifile import version, SUPPORTED_EXTENSIONS
from unifile.pipeline import extract_to_table
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

    sub = p.add_subparsers(dest="cmd", required=True)

    # extract
    ep = sub.add_parser("extract", help="Extract from a file path or URL into a standardized table.")
    ep.add_argument("src", help="Path to a local file OR a URL (http/https).")
    ep.add_argument(
        "--out",
        help="Optional output file for the standardized table. "
             "Extensions: .csv, .parquet, .jsonl. Defaults to printing to stdout.",
    )
    ep.add_argument("--ocr-lang", default="eng", help="OCR language for images and OCR fallback (default: eng).")
    ep.add_argument("--no-ocr", action="store_true", help="Disable OCR fallback for PDFs (vector text only).")
    ep.add_argument("--max-rows", type=int, default=None, help="Limit number of rows printed to stdout.")
    ep.add_argument("--max-colwidth", type=int, default=120, help="Max col width when printing to stdout.")

    # list types
    lp = sub.add_parser("list-types", help="List supported file extensions.")
    lp.add_argument("--one-per-line", action="store_true", help="Print one extension per line.")

    return p


def _save_df(df: pd.DataFrame, out: Path) -> None:
    sfx = out.suffix.lower()
    if sfx == ".csv":
        df.to_csv(out, index=False)
    elif sfx == ".parquet":
        df.to_parquet(out, index=False)
    elif sfx == ".jsonl":
        df.to_json(out, orient="records", lines=True, force_ascii=False)
    else:
        raise ValueError(f"Unsupported output format '{sfx}'. Use .csv, .parquet, or .jsonl")


def _print_df(df: pd.DataFrame, max_rows: Optional[int], max_colwidth: int) -> None:
    with pd.option_context("display.max_rows", max_rows or 20, "display.max_colwidth", max_colwidth):
        print(df.to_string())


def main(argv: Optional[list[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(argv)

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

        # Configure OCR fallback for PDF by temporarily patching the registry factory
        # NOTE: keep API stable; pipeline controls OCR defaults internally.
        # Users can toggle PDF OCR fallback with --no-ocr (handled via env var style flag).
        # To keep it simple, we pass through via environment variable read by extractor.
        import os
        os.environ["UNIFILE_OCR_LANG"] = args.ocr_lang
        os.environ["UNIFILE_DISABLE_PDF_OCR"] = "1" if args.no_ocr else ""

        df = extract_to_table(path)

        if args.out:
            out = Path(args.out)
            _save_df(df, out)
            print(f"Saved standardized table -> {out}")
        else:
            _print_df(df, max_rows=args.max_rows, max_colwidth=args.max_colwidth)

        if tmp_download and tmp_download.exists():
            try:
                tmp_download.unlink()
            except Exception:
                pass

        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())