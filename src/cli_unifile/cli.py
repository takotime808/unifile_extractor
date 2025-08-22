# Copyright (c) 2025 takotime808

from __future__ import annotations

import sys
import argparse
import pandas as pd
from pathlib import Path
from typing import Optional

from unifile import version, SUPPORTED_EXTENSIONS
from unifile.pipeline import extract_to_table, set_runtime_options
from unifile.outputs import write_df, export_html

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


def _looks_like_input(token: str) -> bool:
    """Decide if the first token is a path/URL we should treat as an input."""
    if token.startswith(("http://", "https://")):
        return True
    p = Path(token)
    if p.exists() and p.is_file():
        return True
    # Allow extension-only detection (enables files-first UX)
    if p.suffix:
        ext = p.suffix.lower().lstrip(".")
        return ext in set(SUPPORTED_EXTENSIONS)
    return False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="unifile",
        description="Unified text extraction CLI: ingest docs/images/spreadsheets/HTML/media and emit a standardized table.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {version()}")

    sub = p.add_subparsers(dest="cmd", required=False)

    # extract
    ep = sub.add_parser("extract", help="Extract from a file path or URL into a standardized table.")

    # INPUT
    ep.add_argument("src", nargs="?", help="Path to a local file OR a URL (http/https).")

    # Quality & layout
    ep.add_argument("--disable-tables", action="store_true", help="Disable table extraction")
    ep.add_argument("--disable-block-types", action="store_true", help="Disable structural block typing")
    ep.add_argument("--metadata-mode", choices=["basic", "full"], default=None, help="Metadata richness hint")

    # OCR / PDF
    ep.add_argument("--ocr-lang", default=None, help="OCR language for images and PDF OCR fallback (e.g. eng, deu)")
    ep.add_argument("--no-ocr", action="store_true", help="Disable OCR fallback for PDFs (vector text only)")

    # ASR / Media
    ep.add_argument("--asr-backend", choices=["auto", "dummy", "whisper", "faster-whisper", "whispercpp"],
                    default=None, help="ASR backend (if media extractors are installed)")
    ep.add_argument("--asr-model", default=None, help="ASR model name (e.g., small, medium)")
    ep.add_argument("--asr-device", default=None, help="ASR device (cpu|cuda)")
    ep.add_argument("--asr-compute-type", default=None, help="faster-whisper compute type (e.g., float16)")
    ep.add_argument("--media-chunk-seconds", type=int, default=None, help="Target seconds per ASR chunk")

    # Outputs & downstream use
    ep.add_argument("--out", help="Write output to sink inferred from suffix: .csv | .jsonl | .sqlite | .parquet")
    ep.add_argument("--out-table", default="unifile", help="SQLite table name (when --out ends with .sqlite)")
    ep.add_argument("--html-export", help="Also write a simple HTML rendering of extracted blocks/tables")

    ep.add_argument("--rag-target-chars", type=int, default=None, help="Chunk text for RAG (approx char length)")
    ep.add_argument("--rag-overlap", type=int, default=100, help="Overlap (chars) between RAG chunks")

    # Preview
    ep.add_argument("--max-rows", type=int, default=None, help="Limit number of rows printed to stdout.")
    ep.add_argument("--max-colwidth", type=int, default=120, help="Max col width when printing to stdout.")

    # list types
    lp = sub.add_parser("list-types", help="List supported file extensions.")
    lp.add_argument("--one-per-line", action="store_true", help="Print one extension per line.")

    return p


def _print_df(df: pd.DataFrame, max_rows: Optional[int], max_colwidth: int) -> None:
    with pd.option_context("display.max_rows", max_rows or 20, "display.max_colwidth", max_colwidth):
        print(df.to_string(index=False))


def _preprocess_argv_for_files_first(argv: list[str]) -> list[str]:
    """
    If the user ran `unifile <path-or-url> ...`, auto-insert 'extract' so it behaves
    like the pipeline one-liner UX.
    """
    if not argv:
        return argv
    first = argv[0]
    if first in ("extract", "list-types", "--version", "-h", "--help"):
        return argv
    if _looks_like_input(first):
        return ["extract"] + argv
    return argv


def _guess_name_for_url(src: str) -> str:
    """
    Derive a filename from URL, falling back to an extension based on Content-Type.
    Guarantees a usable extension for the pipeline (.html default).
    """
    from urllib.parse import urlparse

    url_path = Path(urlparse(src).path)
    name = url_path.name

    # If URL doesn't end with a filename.ext, try to infer via HEAD content-type
    if not name or "." not in name:
        guessed = "downloaded.html"  # sensible default for webpages
        if requests is not None:
            try:
                head = requests.head(src, timeout=30, allow_redirects=True)
                ctype = head.headers.get("content-type", "")
                ct = ctype.lower()
                if "pdf" in ct:
                    guessed = "downloaded.pdf"
                elif "json" in ct:
                    guessed = "downloaded.json"
                elif "text/plain" in ct:
                    guessed = "downloaded.txt"
                elif "spreadsheet" in ct or "excel" in ct:
                    guessed = "downloaded.xlsx"
                elif "csv" in ct:
                    guessed = "downloaded.csv"
                elif "image/" in ct:
                    # pick common suffix
                    if "png" in ct:
                        guessed = "downloaded.png"
                    elif "jpeg" in ct or "jpg" in ct:
                        guessed = "downloaded.jpg"
                    elif "webp" in ct:
                        guessed = "downloaded.webp"
                    elif "tiff" in ct:
                        guessed = "downloaded.tiff"
                    else:
                        guessed = "downloaded.img"
                # else keep .html as default
            except Exception:
                pass
        name = guessed

    return name


def main(argv: Optional[list[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    argv = _preprocess_argv_for_files_first(list(argv))
    args = build_parser().parse_args(argv)

    if args.cmd == "list-types":
        if args.one_per_line:
            for ext in SUPPORTED_EXTENSIONS:
                print(ext)
        else:
            print(", ".join(SUPPORTED_EXTENSIONS))
        return 0

    if args.cmd == "extract":
        if not args.src:
            print("error: missing input file or URL", file=sys.stderr)
            return 2

        src = args.src
        tmp_download: Optional[Path] = None

        # Detect URL vs file
        if src.startswith(("http://", "https://")):
            name = _guess_name_for_url(src)
            tmp_download = Path.cwd() / f"unifile_download_{name}"
            _download(src, tmp_download)
            path = tmp_download
        else:
            path = Path(src)
            if not path.exists():
                print(f"error: file not found: {path}", file=sys.stderr)
                return 2

        # Set global/runtime options so class-based extractors and media backends read them uniformly
        set_runtime_options(
            enable_tables=None if args.disable_tables is False else (not args.disable_tables),
            enable_block_types=None if args.disable_block_types is False else (not args.disable_block_types),
            metadata_mode=args.metadata_mode,
            ocr_lang=args.ocr_lang,
            no_ocr=args.no_ocr,
            asr_backend=args.asr_backend,
            asr_model=args.asr_model,
            asr_device=args.asr_device,
            asr_compute_type=args.asr_compute_type,
            media_chunk_seconds=args.media_chunk_seconds,
        )

        # Run extraction (HTML/TXT handled by function-based extractors in pipeline)
        df = extract_to_table(
            path,
            enable_tables=None if args.disable_tables is False else (not args.disable_tables),
            enable_block_types=None if args.disable_block_types is False else (not args.disable_block_types),
            metadata_mode=args.metadata_mode,
            ocr_lang=args.ocr_lang,
            no_ocr=args.no_ocr,
            asr_backend=args.asr_backend,
            asr_model=args.asr_model,
            asr_device=args.asr_device,
            asr_compute_type=args.asr_compute_type,
            media_chunk_seconds=args.media_chunk_seconds,
        )

        # Optional RAG chunking
        if args.rag_target_chars:
            from unifile.outputs import rag_chunk_df  # lazy import to avoid import-time deps
            df = rag_chunk_df(df, target_chars=args.rag_target_chars, overlap=args.rag_overlap)

        # Optional HTML export
        if args.html_export:
            export_html(df, args.html_export, title=f"Unifile Export – {Path(src).name}")
            print(f"Saved HTML export -> {args.html_export}")

        # Output or pretty-print
        if args.out:
            write_df(df, args.out, table=args.out_table)
            print(f"Saved standardized table -> {args.out}")
        else:
            _print_df(df, max_rows=args.max_rows, max_colwidth=args.max_colwidth)

        if tmp_download and tmp_download.exists():
            try:
                tmp_download.unlink()
            except Exception:
                pass

        return 0

    # Fallback (should not reach)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
