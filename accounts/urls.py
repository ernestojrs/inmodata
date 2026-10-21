from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .forms import EmailOrUsernameAuthenticationForm
from . import views

app_name = "accounts"

urlpatterns = [
     path(
        "crear/",
        views.sign_up,
        name="signup",
    ),
    path(
        "iniciar-sesion/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            authentication_form=EmailOrUsernameAuthenticationForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),

        path(
        "recuperar-contrasena/",
        views.ResendPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "recuperar-contrasena/enviado/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "restablecer-contrasena/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "restablecer-contrasena/completado/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    path(
        "verificacion-enviada/",
        views.verification_sent,
        name="verification_sent",
    ),
    path(
        "verificar/<uuid:token>/",
        views.verify_email,
        name="verify_email",
    ),
    path(
        "registro-completado/",
        views.signup_complete,
        name="signup_complete",
    ),
    path(
        "reenviar-verificacion/",
        views.resend_verification,
        name="resend_verification",
    ),
    path(
        "cerrar-sesion/",
        auth_views.LogoutView.as_view(
            next_page=reverse_lazy("home"),
        ),
        name="logout",
    ),
]
