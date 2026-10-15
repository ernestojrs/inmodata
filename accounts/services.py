import requests

from django.conf import settings
from django.urls import reverse


class EmailDeliveryError(Exception):
    """Raised when the verification email could not be handed to Resend."""


def send_verification_email(request, verification):
    """Send the current verification token through Resend's HTTPS API."""

    if not settings.RESEND_API_KEY:
        raise EmailDeliveryError(
            "El envío de correos todavía no está configurado."
        )

    verification_url = request.build_absolute_uri(
        reverse(
            "accounts:verify_email",
            kwargs={"token": verification.token},
        )
    )

    payload = {
        "from": settings.EMAIL_FROM,
        "to": [verification.user.email],
        "subject": "Confirma tu correo electrónico de InmoData",
        "html": (
            "<h1>Confirma tu correo electrónico</h1>"
            "<p>Para activar tu cuenta gratuita de InmoData, "
            "confirma que este correo es tuyo.</p>"
            f'<p><a href="{verification_url}">Confirmar mi correo</a></p>'
            "<p>Este enlace vence en "
            f"{settings.EMAIL_VERIFICATION_MAX_AGE_HOURS} horas.</p>"
            "<p>Si no creaste esta cuenta, puedes ignorar este correo.</p>"
        ),
    }

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise EmailDeliveryError(
            "No se pudo enviar el correo de verificación."
        ) from error
