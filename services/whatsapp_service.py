from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class WhatsAppSendResult:
    success: bool
    provider: str = "twilio"
    message_id: str | None = None
    error: str | None = None


def _with_whatsapp_prefix(number: str) -> str:
    number = number.strip()
    return number if number.startswith("whatsapp:") else f"whatsapp:{number}"


def send_whatsapp_message(phone_number: str, body: str) -> WhatsAppSendResult:
    """
    Send a WhatsApp message via Twilio.

    Credentials are read from environment variables. The import happens lazily
    so local validation can run before Twilio is installed.
    """
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_WHATSAPP_FROM")

    if not account_sid or not auth_token or not from_number:
        return WhatsAppSendResult(
            success=False,
            error=(
                "Twilio WhatsApp credentials are not configured. Set "
                "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_WHATSAPP_FROM."
            ),
        )

    try:
        from twilio.rest import Client
    except ModuleNotFoundError as exc:
        return WhatsAppSendResult(
            success=False,
            error=f"Twilio package is not installed: {exc}",
        )

    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            from_=_with_whatsapp_prefix(from_number),
            to=_with_whatsapp_prefix(phone_number),
            body=body,
        )
        return WhatsAppSendResult(
            success=True,
            message_id=getattr(message, "sid", None),
        )
    except Exception as exc:
        return WhatsAppSendResult(success=False, error=str(exc))
