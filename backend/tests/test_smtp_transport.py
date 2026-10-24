"""Isolated SMTP contract tests: no sockets, credentials, database or provider calls.

Runnable without application/database dependencies:
    python -m unittest discover -s tests -p test_smtp_transport.py -v
Also collected by the normal backend pytest suite.
"""
import os
import ssl
import unittest
from unittest.mock import patch

from app.security import customer_auth as ca


class SmtpTransportTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AUTH_CODE_PROVIDER": "smtp",
            "SMTP_HOST": "smtp.example.test",
            "SMTP_FROM": "login@example.test",
            "SMTP_USER": "synthetic-user",
            "SMTP_PASSWORD": "synthetic-test-password",  # secrets-scan: allow (synthetic)
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.events = []
        self.tls_error = None
        self.refused = {}
        outer = self

        class Relay:
            def __init__(self, host, port, timeout):
                outer.events.append("connect")

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                outer.events.append("close")

            def starttls(self, *, context):
                outer.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
                outer.assertTrue(context.check_hostname)
                outer.events.append("verified_tls")
                if outer.tls_error:
                    raise outer.tls_error

            def login(self, user, password):
                outer.events.append("login")

            def send_message(self, message):
                outer.events.append("send")
                return outer.refused

        self.relay = Relay

    def deliver(self):
        return ca.deliver_code("email", "owned@example.test", "123456", smtp_factory=self.relay)

    def test_verifies_relay_before_credentials_and_code(self):
        self.assertEqual(self.deliver(), {"status": "SENT", "provider": "smtp"})
        self.assertEqual(self.events, ["connect", "verified_tls", "login", "send", "close"])

    def test_invalid_certificate_never_sends_credentials_or_code(self):
        self.tls_error = ssl.SSLCertVerificationError("untrusted synthetic certificate")
        self.assertEqual(self.deliver()["status"], "FAILED")
        self.assertEqual(self.events, ["connect", "verified_tls", "close"])

    def test_hostname_mismatch_never_sends_credentials_or_code(self):
        self.tls_error = ssl.SSLCertVerificationError("synthetic hostname mismatch")
        self.assertEqual(self.deliver()["status"], "FAILED")
        self.assertNotIn("login", self.events)
        self.assertNotIn("send", self.events)

    def test_tls_error_detail_does_not_echo_private_data(self):
        self.tls_error = ssl.SSLError("123456 synthetic-test-password")
        result = self.deliver()
        self.assertEqual(result["status"], "FAILED")
        self.assertNotIn("123456", repr(result))
        self.assertNotIn("synthetic-test-password", repr(result))

    def test_refused_recipient_is_not_reported_sent(self):
        self.refused = {"owned@example.test": (550, b"refused")}
        result = self.deliver()
        self.assertEqual(result["status"], "FAILED")
        self.assertNotIn("owned@example.test", repr(result))


if __name__ == "__main__":
    unittest.main()
