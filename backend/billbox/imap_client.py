from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header
from email.utils import mktime_tz, parsedate_tz
import hashlib
import imaplib
import ssl
from typing import Any

from bs4 import BeautifulSoup


@dataclass(frozen=True, slots=True)
class MailMessage:
    uid: int
    sender: str
    subject: str
    received_at: datetime
    text: str
    message_id: str
    content_sha256: str


def _decode_header(value: str | None) -> str:
    parts: list[str] = []
    for item, encoding in decode_header(value or ""):
        if isinstance(item, bytes):
            parts.append(item.decode(encoding or "utf-8", errors="replace"))
        else:
            parts.append(item)
    return "".join(parts)


def _message_text(message: Any) -> str:
    html = ""
    plain = ""
    parts = message.walk() if message.is_multipart() else (message,)
    for part in parts:
        disposition = str(part.get("Content-Disposition") or "")
        if "attachment" in disposition.casefold():
            continue
        content_type = part.get_content_type()
        if content_type not in {"text/html", "text/plain"}:
            continue
        payload = part.get_payload(decode=True) or b""
        value = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if content_type == "text/html":
            html = value
        elif not plain:
            plain = value
    text = BeautifulSoup(html, "html.parser").get_text("\n") if html else plain
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


class ImapClient:
    def __init__(self, user: str, password: str, server: str, port: int = 993):
        self.user = user
        self.password = password
        self.server = server
        self.port = port
        self.connection: imaplib.IMAP4_SSL | None = None
        self.uid_validity = 0

    def connect(self) -> "ImapClient":
        context = ssl.create_default_context()
        connection = imaplib.IMAP4_SSL(
            self.server, self.port, ssl_context=context, timeout=15
        )
        connection.login(self.user, self.password)
        status, _ = connection.select("INBOX", readonly=True)
        if status != "OK":
            connection.logout()
            raise ConnectionError("无法选择 IMAP 收件箱")
        _, values = connection.response("UIDVALIDITY")
        if not values or not values[0]:
            connection.logout()
            raise ConnectionError("IMAP 服务器没有返回 UIDVALIDITY")
        self.uid_validity = int(values[0])
        self.connection = connection
        return self

    def close(self) -> None:
        connection = self.connection
        self.connection = None
        if connection is not None:
            try:
                connection.logout()
            except imaplib.IMAP4.error:
                pass

    def search(self, keyword: str, limit: int) -> list[int]:
        if self.connection is None:
            raise RuntimeError("IMAP client is not connected")
        try:
            status, data = self.connection.uid(
                "search", None, "SUBJECT", f'"{keyword}"'.encode("utf-8")
            )
        except UnicodeEncodeError:
            status, data = self.connection.uid(
                "search", None, "SUBJECT", f'"{keyword}"'.encode("gb18030")
            )
        if status != "OK" or not data or not data[0]:
            return []
        return [int(uid) for uid in data[0].split()[-limit:]][::-1]

    def fetch(self, uid: int) -> MailMessage:
        if self.connection is None:
            raise RuntimeError("IMAP client is not connected")
        status, data = self.connection.uid("fetch", str(uid), "(RFC822)")
        if status != "OK":
            raise ConnectionError(f"下载邮件 UID {uid} 失败")
        raw = next(
            (item[1] for item in data if isinstance(item, tuple) and item[1]), None
        )
        if raw is None:
            raise ConnectionError(f"邮件 UID {uid} 没有正文")
        message = message_from_bytes(raw)
        parsed_date = parsedate_tz(message.get("Date"))
        received_at = (
            datetime.fromtimestamp(mktime_tz(parsed_date)).astimezone()
            if parsed_date
            else datetime.now().astimezone()
        )
        return MailMessage(
            uid=uid,
            sender=_decode_header(message.get("From")),
            subject=_decode_header(message.get("Subject")),
            received_at=received_at,
            text=_message_text(message),
            message_id=str(message.get("Message-ID") or ""),
            content_sha256=hashlib.sha256(raw).hexdigest(),
        )
