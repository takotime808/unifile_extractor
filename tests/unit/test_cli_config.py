from pathlib import Path
import pandas as pd
import cli_unifile.cli as cli


def test_config_file_controls_runtime(tmp_path, monkeypatch):
    monkeypatch.delenv('UNIFILE_OCR_LANG', raising=False)
    monkeypatch.delenv('UNIFILE_DISABLE_PDF_OCR', raising=False)
    cfg = tmp_path / "cfg.toml"
    cfg.write_text("""[extract]
ocr_lang='spa'
no_ocr=true
""")

    called = {}

    def fake_extract(path, ocr_lang=None, no_ocr=None):
        called['ocr_lang'] = ocr_lang
        called['no_ocr'] = no_ocr
        return pd.DataFrame()

    monkeypatch.setattr(cli, 'extract_to_table', fake_extract)
    monkeypatch.setattr(cli, '_print_df', lambda *a, **k: None)
    sample = tmp_path / 't.txt'
    sample.write_text('hi')
    rc = cli.main(['--config', str(cfg), 'extract', str(sample)])
    assert rc == 0
    assert called['ocr_lang'] == 'spa'
    assert called['no_ocr'] is True


def test_env_overrides_config(tmp_path, monkeypatch):
    monkeypatch.delenv('UNIFILE_OCR_LANG', raising=False)
    monkeypatch.delenv('UNIFILE_DISABLE_PDF_OCR', raising=False)
    cfg = tmp_path / 'cfg.toml'
    cfg.write_text("""[extract]
ocr_lang='spa'
""")

    called = {}
    def fake_extract(path, ocr_lang=None, no_ocr=None):
        called['ocr_lang'] = ocr_lang
        called['no_ocr'] = no_ocr
        return pd.DataFrame()

    monkeypatch.setattr(cli, 'extract_to_table', fake_extract)
    monkeypatch.setattr(cli, '_print_df', lambda *a, **k: None)
    monkeypatch.setenv('UNIFILE_OCR_LANG', 'ita')
    sample = tmp_path / 't.txt'
    sample.write_text('hi')
    rc = cli.main(['--config', str(cfg), 'extract', str(sample)])
    assert rc == 0
    assert called['ocr_lang'] == 'ita'
