# Recipes

## Batch a directory to Parquet
Extract every supported file in a directory and write a single Parquet file:

```bash
python examples/batch_to_parquet.py ./docs/sources/_static/data ./batch.parquet
```

## OCR only scanned PDFs
The extractor automatically checks PDF pages for embedded text. Pages with text are parsed directly; pages without text are rasterized and sent to Tesseract. Simply run:

```bash
unifile extract scanned_pdfs/*.pdf --out scans.parquet
```

To disable the fallback OCR entirely use `--no-ocr`.

## Extract emails with attachments
Process a directory of `.eml` files, including attachments as sub-rows:

```bash
unifile extract inbox/*.eml --out mail.parquet
```

## Video lower-thirds via keyframe OCR
Sample video frames on a fixed interval and run OCR to capture lower-third titles:

```bash
unifile extract show.mp4 --frame-interval 2.0 --ocr-langs=eng+spa --out lower_thirds.jsonl
```

The `timestamp` for each frame is stored in the metadata.
