# Copyright (c) 2025 takotime808

from __future__ import annotations

from pathlib import Path
from typing import List
from email import policy
from email.parser import BytesParser

from unifile.extractors.base import (
    BaseExtractor,
    make_row,
    Row,
)


class EmlExtractor(BaseExtractor):
    """Extractor for EML (email) files.

    This extractor parses raw EML files, extracts headers, message body
    text, and a simple list of attachments. Multipart messages are
    supported, with text parts concatenated together. Non-text parts are
    ignored except for attachment filenames.
    """
    supported_extensions = ["eml"]

    def _extract(self, path: Path) -> List[Row]:
        """Extract plain text and metadata from an EML file.

        The extractor parses the email using the ``email`` package with the
        default policy. It collects header fields such as subject, sender,
        recipients, CC, and date. If the message is multipart, it walks all
        parts, concatenating text content and recording attachment filenames.

        Args:
            path (Path): Path to the EML file.

        Returns:
            List[Row]: A list containing one row with:
                - source type: ``eml``
                - level: ``file``
                - section: ``body``
                - text: Concatenated plain text body of the email
                - metadata: Dictionary with:
                    - ``"subject"``: Subject line
                    - ``"from"``: Sender address
                    - ``"to"``: Recipient(s)
                    - ``"cc"``: CC recipients
                    - ``"date"``: Date string
                    - ``"attachments"``: List of attachment filenames
                - status: ``"ok"``
        """
        data = path.read_bytes()
        msg = BytesParser(policy=policy.default).parsebytes(data)

        subject = msg.get("Subject", "")
        sender = msg.get("From", "")
        to = msg.get("To", "")
        cc = msg.get("Cc", "")
        date = msg.get("Date", "")

        parts_text = []
        attachments = []
        if msg.is_multipart():
            for part in msg.walk():
                cdisp = (part.get("Content-Disposition") or "").lower()
                ctype = (part.get_content_type() or "").lower()
                if cdisp.startswith("attachment"):
                    attachments.append(part.get_filename() or "attachment")
                elif ctype.startswith("text/"):
                    try:
                        parts_text.append(part.get_content())
                    except Exception:
                        pass
        else:
            try:
                parts_text.append(msg.get_content())
            except Exception:
                pass

        content = "\n".join(t for t in parts_text if t)
        meta = {
            "subject": subject, "from": sender, "to": to, "cc": cc, "date": date,
            "attachments": attachments,
        }
        return [make_row(path, "eml", "file", "body", content, meta, status="ok")]
