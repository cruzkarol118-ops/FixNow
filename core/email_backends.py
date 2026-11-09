"""Django email backend for Brevo's HTTPS transactional email API."""

import base64
import json
import logging
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class BrevoAPIEmailBackend(BaseEmailBackend):
    """Send Django EmailMessage objects through Brevo over HTTPS (port 443)."""

    endpoint = "https://api.brevo.com/v3/smtp/email"

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.api_key = getattr(settings, "BREVO_API_KEY", "")
        self.timeout = getattr(settings, "EMAIL_TIMEOUT", 15)

    @staticmethod
    def _address(value):
        name, address = parseaddr(value or "")
        result = {"email": address}
        if name:
            result["name"] = name
        return result

    def _payload(self, message):
        sender = self._address(message.from_email or settings.DEFAULT_FROM_EMAIL)
        payload = {
            "sender": sender,
            "to": [self._address(address) for address in message.to],
            "subject": message.subject or "",
        }

        if message.content_subtype == "html":
            payload["htmlContent"] = message.body
        else:
            payload["textContent"] = message.body

        for content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                payload["htmlContent"] = content
            elif mimetype == "text/plain":
                payload["textContent"] = content

        if message.cc:
            payload["cc"] = [self._address(address) for address in message.cc]
        if message.bcc:
            payload["bcc"] = [self._address(address) for address in message.bcc]
        if message.reply_to:
            payload["replyTo"] = self._address(message.reply_to[0])

        attachments = []
        for attachment in message.attachments:
            if isinstance(attachment, dict):
                content = attachment["content"]
                filename = attachment["name"]
                mimetype = attachment.get("contentType")
            else:
                filename, content, mimetype = attachment
            if isinstance(content, str):
                content = content.encode()
            item = {
                "name": filename,
                "content": base64.b64encode(content).decode("ascii"),
            }
            if mimetype:
                item["contentType"] = mimetype
            attachments.append(item)
        if attachments:
            payload["attachment"] = attachments
        return payload

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            logger.error("Brevo API backend selected but BREVO_API_KEY is empty")
            if self.fail_silently:
                return 0
            raise RuntimeError("BREVO_API_KEY is not configured")

        sent = 0
        for message in email_messages:
            if not message.recipients():
                continue
            request = Request(
                self.endpoint,
                data=json.dumps(self._payload(message)).encode("utf-8"),
                headers={
                    "api-key": self.api_key,
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    if 200 <= response.status < 300:
                        sent += 1
                    else:
                        logger.error("Brevo API returned HTTP %s", response.status)
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                # Never log the request headers or API key.
                logger.error("Brevo API email send failed: %s", exc)
                if not self.fail_silently:
                    raise
        return sent
