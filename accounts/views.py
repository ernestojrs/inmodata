import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import login, views as auth_views
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import SignUpForm,ResendPasswordResetForm
from .models import EmailVerification
from .services import EmailDeliveryError, send_verification_email
from django.urls import reverse_lazy


class ResendPasswordResetView(auth_views.PasswordResetView):
    form_class = ResendPasswordResetForm
    template_name = "accounts/password_reset.html"
    success_url = reverse_lazy("accounts:password_reset_done")

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except EmailDeliveryError:
            form.add_error(
                None,
                "No pudimos enviar el enlace. Inténtalo de nuevo en unos minutos.",
            )
            return self.form_invalid(form)



def _safe_next_url(request):
    next_url = request.POST.get("next") or request.GET.get("next", "")

    if url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
    ):
        return next_url

    return ""


def sign_up(request):
    next_url = _safe_next_url(request)

    if request.method == "POST":
        form = SignUpForm(request.POST)

        if form.is_valid():
            user = form.save()
            verification = EmailVerification.objects.create(user=user)

            try:
                send_verification_email(request, verification)
            except EmailDeliveryError:
                # Do not leave an account locked when delivery did not start.
                user.delete()
                form.add_error(
                    None,
                    "No pudimos enviar el correo de verificación. "
                    "Inténtalo de nuevo en unos minutos.",
                )
            else:
                verification.sent_at = timezone.now()
                verification.save(update_fields=["sent_at"])
                request.session["signup_next_url"] = next_url
                return redirect("accounts:verification_sent")
    else:
        form = SignUpForm()

    return render(
        request,
        "accounts/signup.html",
        {
            "form": form,
            "next": next_url,
        },
    )


def verification_sent(request):
    return render(request, "accounts/verification_sent.html")


def verify_email(request, token):
    verification = get_object_or_404(EmailVerification, token=token)
    expires_at = verification.created_at + timedelta(
        hours=settings.EMAIL_VERIFICATION_MAX_AGE_HOURS
    )

    if timezone.now() > expires_at:
        return render(
            request,
            "accounts/verification_invalid.html",
            {"expired": True},
            status=400,
        )

    if verification.verified_at:
        return render(
            request,
            "accounts/verification_invalid.html",
            {"expired": False},
            status=400,
        )

    user = verification.user
    user.is_active = True
    user.save(update_fields=["is_active"])
    verification.verified_at = timezone.now()
    verification.save(update_fields=["verified_at"])

    login(request, user, backend="accounts.backends.EmailOrUsernameModelBackend")
    request.session["track_verified_signup"] = True
    request.session["verified_signup_next_url"] = request.session.pop(
        "signup_next_url",
        "",
    )

    return redirect("accounts:signup_complete")


def signup_complete(request):
    next_url = request.session.pop("verified_signup_next_url", "")

    if not url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
    ):
        next_url = ""

    return render(
        request,
        "accounts/verification_complete.html",
        {
            "next_url": next_url,
            "track_signup": request.session.pop("track_verified_signup", False),
        },
    )


def resend_verification(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        if email:
            verification = (
                EmailVerification.objects.select_related("user")
                .filter(user__email__iexact=email, verified_at__isnull=True)
                .first()
            )

            if verification and not verification.user.is_active:
                verification.token = uuid.uuid4()
                verification.created_at = timezone.now()
                verification.sent_at = None
                verification.save(
                    update_fields=["token", "created_at", "sent_at"]
                )

                try:
                    send_verification_email(request, verification)
                except EmailDeliveryError:
                    # Keep this response identical to prevent email enumeration.
                    pass
                else:
                    verification.sent_at = timezone.now()
                    verification.save(update_fields=["sent_at"])

        return redirect("accounts:verification_sent")

    return render(request, "accounts/resend_verification.html")
