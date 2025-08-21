# CLI

Install:
```bash
pip install -e .
```

List supported types:
```bash
unifile list-types --one-per-line
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