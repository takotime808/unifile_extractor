# Examples #

----
## Using Media (Audio and Video Files)

### Install media extras
```bash
pip install -e .[media]
```

### Transcribe an MP3
```bash
unifile extract lecture.mp3 --out transcript.jsonl
```

### Transcribe a video (requires ffmpeg)
```bash
unifile extract interview.mp4 --out transcript.csv --asr-model small --asr-device cpu
```

## Recipes

### Batch a directory to Parquet
```bash
python batch_to_parquet.py ./docs/sources/_static/data output.parquet
```

### OCR only scanned PDFs
```bash
unifile extract scanned_pdfs/*.pdf --out scans.parquet
```

### Extract emails with attachments
```bash
unifile extract inbox/*.eml --out mail.parquet
```

### Video lower-thirds via keyframe OCR
```bash
unifile extract show.mp4 --frame-interval 2.0 --ocr-langs=eng+spa --out lower_thirds.jsonl
```