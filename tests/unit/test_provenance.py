import fitz
from pathlib import Path
from PIL import Image, ImageDraw
import unifile.processing.provenance as prov
from unifile.processing.provenance import extract_provenance


def _build_pdf(path: Path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello")
    doc.save(path)
    doc.close()


def _build_img(path: Path):
    img = Image.new("RGB", (60, 30), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((5, 5), "hi", fill=(0, 0, 0))
    img.save(path)


def test_extract_provenance_pdf(tmp_path):
    p = tmp_path / "sample.pdf"
    _build_pdf(p)
    rows = extract_provenance(p)
    assert rows and rows[0].bbox


def test_extract_provenance_image(tmp_path, monkeypatch):
    p = tmp_path / "img.png"
    _build_img(p)

    class FakePyt:
        class Output:
            DICT = None

        @staticmethod
        def image_to_data(img, lang="eng", output_type=None):
            return {
                "text": ["hi"],
                "left": [1],
                "top": [2],
                "width": [3],
                "height": [4],
            }

    monkeypatch.setattr(prov, "pytesseract", FakePyt)
    rows = extract_provenance(p)
    assert rows[0].bbox == [1, 2, 4, 6]
