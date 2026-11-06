import base64
import json
from unittest.mock import patch

from django.core.mail import EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from .email_backends import GmailApiEmailBackend


class GmailApiEmailBackendTests(SimpleTestCase):
    @staticmethod
    def _response(payload):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        return FakeResponse()

    @override_settings(
        GMAIL_OAUTH_CLIENT_ID="client-id",
        GMAIL_OAUTH_CLIENT_SECRET="client-secret",
        GMAIL_OAUTH_REFRESH_TOKEN="refresh-token",
        EMAIL_TIMEOUT=15,
    )
    @patch("tallermami.email_backends.urlopen")
    def test_envia_correo_html_con_token_oauth(self, mock_urlopen):
        mock_urlopen.side_effect = [
            self._response({"access_token": "access-token"}),
            self._response({"id": "message-id"}),
        ]
        correo = EmailMultiAlternatives(
            subject="Aviso del taller",
            body="Tu vehículo está listo.",
            from_email="Taller Molina Henze <taller@gmail.com>",
            to=["cliente@example.com"],
        )
        correo.attach_alternative(
            "<p>Tu vehículo está listo.</p>",
            "text/html",
        )

        enviado = GmailApiEmailBackend().send_messages([correo])

        self.assertEqual(enviado, 1)
        token_request = mock_urlopen.call_args_list[0].args[0]
        self.assertEqual(
            token_request.full_url,
            "https://oauth2.googleapis.com/token",
        )
        send_request = mock_urlopen.call_args_list[1].args[0]
        self.assertEqual(
            send_request.get_header("Authorization"),
            "Bearer access-token",
        )
        raw_message = json.loads(send_request.data)["raw"]
        decoded_message = base64.urlsafe_b64decode(
            raw_message + "=" * (-len(raw_message) % 4)
        ).decode("utf-8")
        self.assertIn("cliente@example.com", decoded_message)
        self.assertIn("Tu vehículo está listo.", decoded_message)
