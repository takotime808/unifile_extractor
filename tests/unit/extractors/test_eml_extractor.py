import textwrap
from pathlib import Path

from unifile.extractors.eml_extractor import EmlExtractor
from unifile.extractors.msg_extractor import MsgExtractor


def create_eml(tmp_path: Path) -> Path:
    content = textwrap.dedent(
        """\
        From: a@example.com
        To: b@example.com
        Subject: Hi
        MIME-Version: 1.0
        Content-Type: multipart/mixed; boundary="BOUND"

        --BOUND
        Content-Type: text/plain

        Hello body
        --BOUND
        Content-Type: text/plain; name="att.txt"
        Content-Disposition: attachment; filename="att.txt"

        Attachment text
        --BOUND--
        """
    )
    p = tmp_path / "sample.eml"
    p.write_text(content)
    return p


def test_eml_attachment_rows(tmp_path: Path):
    path = create_eml(tmp_path)
    rows = EmlExtractor().extract(path)
    assert len(rows) == 2
    body, attachment = rows
    assert attachment.unit_type == "attachment"
    assert attachment.unit_id == "att.txt"
    assert "Attachment text" in attachment.content
    assert attachment.metadata["filename"] == "att.txt"
    assert "att.txt" in body.metadata["attachments"]


def test_msg_missing_dependency(tmp_path: Path):
    path = tmp_path / "mail.msg"
    path.write_bytes(b"dummy")
    rows = MsgExtractor().extract(path)
    assert rows[0].status == "error"
    assert "extract_msg" in (rows[0].error or "")
