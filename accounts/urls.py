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
