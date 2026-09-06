from __future__ import annotations

import ssl
from unittest.mock import patch


class FakeImapConnection:
    def __init__(self):
        self.uid_calls = []
        self.logged_out = False

    def login(self, user, password):
        self.credentials = (user, password)
        return "OK", [b"logged in"]

    def select(self, mailbox, readonly):
        self.selected = (mailbox, readonly)
        return "OK", [b"1"]

    def response(self, name):
        assert name == "UIDVALIDITY"
        return "UIDVALIDITY", [b"987"]

    def uid(self, command, *args):
        self.uid_calls.append((command, args))
        if command == "search":
            return "OK", [b"1001 1002"]
        return "OK", [
            (
                b"message",
                b"From: CMB <95555@message.cmbchina.com>\r\n"
                b"Subject: Transaction\r\n"
                b"Message-ID: <mail@example>\r\n"
                b"Date: Sun, 06 Sep 2026 08:30:00 +0800\r\n"
                b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
                b"CMB transaction content",
            )
        ]

    def logout(self):
        self.logged_out = True


def test_connection_uses_verified_tls_and_read_only_mailbox():
    from billbox.imap_client import ImapClient

    connection = FakeImapConnection()
    with patch("billbox.imap_client.imaplib.IMAP4_SSL", return_value=connection) as ssl_imap:
        client = ImapClient("owner@example.com", "secret", "imap.example.com")
        client.connect()

    context = ssl_imap.call_args.kwargs["ssl_context"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert connection.selected == ("INBOX", True)
    assert client.uid_validity == 987


def test_search_and_fetch_use_stable_imap_uids():
    from billbox.imap_client import ImapClient

    connection = FakeImapConnection()
    client = ImapClient("owner@example.com", "secret", "imap.example.com")
    client.connection = connection

    uids = client.search("Transaction", 1)
    message = client.fetch(uids[0])
    client.close()

    assert uids == [1002]
    assert message.uid == 1002
    assert message.sender == "CMB <95555@message.cmbchina.com>"
    assert message.subject == "Transaction"
    assert message.message_id == "<mail@example>"
    assert len(message.content_sha256) == 64
    assert connection.logged_out is True
    assert [call[0] for call in connection.uid_calls] == ["search", "fetch"]
