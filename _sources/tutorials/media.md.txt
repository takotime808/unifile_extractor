# Media (Audio and Video Files)

## Install media extras
```bash
pip install -e .[media]
```

## Transcribe an MP3
```bash
unifile extract lecture.mp3 --out transcript.jsonl
```

## Transcribe a video (requires ffmpeg)
```bash
unifile extract interview.mp4 --out transcript.csv --asr-model small --asr-device cpu
```