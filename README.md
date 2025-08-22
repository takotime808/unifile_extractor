<!-- Copyright (c) 2025 takotime808 -->
# Unifile Extractor

[![Docs](https://img.shields.io/badge/docs-online-blue.svg)](https://takotime808.github.io/unifile_extractor/)
![coverage](https://takotime808.github.io/unifile_extractor/_assets/coverage.svg)
<!-- [![coverage](https://img.shields.io/endpoint?url=https://takotime808.github.io/unifile_extractor/_assets/coverage.json)](https://takotime808.github.io/unifile_extractor/) -->

<img src="docs/sources/_static/logos/unifile-favicon.png" alt="drawing" width="100"/>

A pragmatic pipeline that ingests **documents, spreadsheets, images, archives, email, web pages, and even audio/video**  
and extracts text into a **standardized table**.

---

## Features

- **Single function API**:  
  ```python
  extract_to_table(path_or_bytes, filename=...) -> pandas.DataFrame
  ```
- **File types supported (batteries included)**:
  - **Documents**: PDF (with optional OCR), DOCX, PPTX, TXT/MD/RTF/LOG, HTML/HTM  
  - **Spreadsheets & Tables**: XLSX, XLSM, XLTX, XLTM, CSV, TSV  
  - **Images**: PNG, JPG/JPEG, BMP, TIFF, WebP, GIF (OCR via Tesseract)  
  - **Email & Web**: EML, HTML  
  - **Archives / Structured Data** *(optional, `pip install .[archive]`)*: ZIP, TAR, GZ, BZ2, XZ, EPUB, JSON, XML  
  - **Audio & Video** *(optional, `pip install .[media]`)*: WAV, MP3, M4A, FLAC, OGG, WEBM, AAC, MP4, MOV, MKV  
    - Audio/video extractors run ffmpeg for decoding and (optionally) ASR with [Whisper](https://github.com/openai/whisper) or [faster-whisper].
- **Standardized schema**:

| column        | meaning |
|---------------|---------|
| `source_path` | Absolute/real path to the processed file |
| `source_name` | Basename of the file |
| `file_type`   | Extension/normalized type |
| `unit_type`   | Logical unit: `page`, `slide`, `sheet`, `table`, `image`, `file`, `email`, `segment`, ... |
| `unit_id`     | Index or name of the unit (`0`, `1`, `Sheet1`, `body`, etc.) |
| `content`     | Extracted plain text |
| `char_count`  | Character count of `content` |
| `metadata`    | Dict with file/unit-specific metadata (JSON-serializable) |
| `status`      | `ok` or `error` |
| `error`       | Exception or notes when extraction fails |

---

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev,test,docs,archive,media]
```

> **OCR note** (images and scanned PDFs):  
> This project uses [pytesseract](https://pypi.org/project/pytesseract/), which requires the Tesseract binary.  
> - macOS: `brew install tesseract`  
> - Ubuntu/Debian: `sudo apt-get install tesseract-ocr`  
> - Windows: Install Tesseract from UB Mannheim builds and add to PATH.

---

## Usage (Python)

### Extract from a file
```python
from unifile import extract_to_table

df = extract_to_table("/path/to/file.pdf")
print(df.head())
df.to_csv("out.csv", index=False)
```

### Extract from bytes
```python
with open("/path/to/image.png", "rb") as f:
    data = f.read()

df = extract_to_table(data, filename="image.png")
```

### Audio/Video
```python
df = extract_to_table("meeting.mp3")
print(df[["unit_id", "content", "metadata"]].head())
```

---

## CLI

Install:
```bash
pip install -e .
```

List supported types:
```bash
unifile list-types --one-per-line
```

Obtain an HTML file and use the CLI to extract the contents:
```bash
# curl a file to use
curl -L https://www.python.org -o python.html

# Main command
unifile python.html --out results.jsonl --html-export extracted.html
```

Extract from a local file and print to stdout:
```bash
unifile extract ./docs/sources/_static/data/sample-engineering-drawing.pdf --max-rows 50 --max-colwidth 120
```

Extract from a URL and save to JSONL:
```bash
unifile extract "https://example.com/sample.pdf" --out result.jsonl
```

Extract from a URL and save to Parquet:
```bash
unifile extract "https://www.fastradius.com/wp-content/uploads/2022/02/sample-engineering-drawing.pdf" --out drawing.parquet
```

Control OCR (disable PDF OCR fallback and set OCR language):
```bash
unifile extract ./scan.pdf --no-ocr --ocr-lang eng
```

Output formats: `.csv`, `.parquet`, `.jsonl`.

---

## Design notes

- **PDF**: Uses PyMuPDF; if text is empty, falls back to OCR (configurable).
- **DOCX**: Collects paragraphs & table text.
- **PPTX**: Extracts from slide shapes with `.text`.
- **Spreadsheets**: Serializes rows with tab-delimiters.
- **HTML**: Uses BeautifulSoup; preserves block breaks.
- **Text files**: Attempts encoding detection via `chardet`.
- **Archives/EPUB/JSON/XML**: Optional extras add decompression/parsing.
- **Audio/Video**: Runs ffmpeg to decode; can run Whisper ASR to transcribe into text rows.

---

## Example

```python
from unifile import extract_to_table
df = extract_to_table("lecture.mkv")
df.to_parquet("lecture.parquet", index=False)
```

---

## Development & Testing

```bash
pytest --maxfail=1 --disable-warnings -q
```

- Unit tests mock heavy OCR/ASR/ffmpeg calls for fast CI.  
- Integration tests validate full end-to-end pipeline.  
- Docs are built with Sphinx + Furo theme.

---

## Limits & Tips

- OCR depends on image resolution (PDF rasterized @ 2x scale).
- Audio/Video transcription requires ffmpeg and Whisper (CPU/GPU performance may vary).
- Very large spreadsheets/PDFs produce large outputs; consider chunking.
