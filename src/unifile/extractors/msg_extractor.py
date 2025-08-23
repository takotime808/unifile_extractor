"""Outlook `.msg` extractor."""

from __future__ import annotations

from pathlib import Path
from typing import List

from unifile.extractors.base import BaseExtractor, Row, make_row


class MsgExtractor(BaseExtractor):
    """Extractor for Microsoft Outlook ``.msg`` files.

    The implementation relies on the optional :mod:`extract_msg` package.  When
    the dependency is not available a single ``error`` row is returned.  When
    installed, the extractor retrieves the message headers, plain text body and
    a list of attachments.  Attachment names are exposed as ``attachment``
    sub-rows without attempting to decode binary content.
    """

    supported_extensions = ["msg"]

    def _extract(self, path: Path) -> List[Row]:  # pragma: no cover - import guarded
        try:
            import extract_msg  # type: ignore
        except Exception as e:  # pragma: no cover - simple fallback
            return [
                make_row(
                    path,
                    "msg",
                    "file",
                    "body",
                    "",
                    {},
                    status="error",
                    error="missing extract_msg",
                )
            ]

        msg = extract_msg.Message(str(path))
        body = msg.body or ""
        attachments = [
            att.longFilename or att.shortFilename or "attachment" for att in msg.attachments
        ]

        meta = {
            "subject": msg.subject,
            "from": msg.sender,
            "to": msg.to,
            "date": msg.date,
            "attachments": attachments,
        }

        rows: List[Row] = [make_row(path, "msg", "file", "body", body, meta, status="ok")]
        for name in attachments:
            rows.append(
                make_row(
                    path,
                    "msg",
                    "attachment",
                    name,
                    "",
                    {"filename": name},
                    status="ok",
                )
            )
        return rows
