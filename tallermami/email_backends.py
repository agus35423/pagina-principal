import base64
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class GmailApiError(Exception):
    pass


class GmailApiEmailBackend(BaseEmailBackend):
    token_url = "https://oauth2.googleapis.com/token"
    send_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        try:
            access_token = self._get_access_token()
        except GmailApiError:
            if not self.fail_silently:
                raise
            return 0

        sent = 0
        for email_message in email_messages:
            try:
                self._send_message(email_message, access_token)
            except GmailApiError:
                if not self.fail_silently:
                    raise
            else:
                sent += 1
        return sent

    def _get_access_token(self):
        data = urlencode(
            {
                "client_id": settings.GMAIL_OAUTH_CLIENT_ID,
                "client_secret": settings.GMAIL_OAUTH_CLIENT_SECRET,
                "refresh_token": settings.GMAIL_OAUTH_REFRESH_TOKEN,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        request = Request(
            self.token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = self._post_json(request)
        access_token = response.get("access_token")
        if not access_token:
            raise GmailApiError(
                "Google OAuth no devolvió un token de acceso."
            )
        return access_token

    def _send_message(self, email_message, access_token):
        raw_message = base64.urlsafe_b64encode(
            email_message.message().as_bytes()
        ).decode("ascii").rstrip("=")
        request = Request(
            self.send_url,
            data=json.dumps({"raw": raw_message}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )
        response = self._post_json(request)
        if not response.get("id"):
            raise GmailApiError(
                "Gmail API no confirmó la aceptación del mensaje."
            )

    def _post_json(self, request):
        try:
            with urlopen(request, timeout=settings.EMAIL_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detalle = error.read().decode("utf-8", errors="replace")
            raise GmailApiError(
                f"Gmail API rechazó la solicitud (HTTP {error.code}): "
                f"{detalle}"
            ) from error
        except (URLError, TimeoutError) as error:
            raise GmailApiError(
                f"No se pudo conectar con Gmail API: {error}"
            ) from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GmailApiError(
                "Gmail API devolvió una respuesta que no se pudo interpretar."
            ) from error
