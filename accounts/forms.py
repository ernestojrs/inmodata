from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordResetForm
from django.db.models import Q
from django.urls import reverse
from .services import send_password_reset_email


User = get_user_model()


class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        label="Correo electrónico",
        help_text="Te enviaremos un enlace para confirmar que es tu correo.",
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "inputmode": "email",
            }
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_username(self):
        username = super().clean_username().strip()

        if User.objects.filter(
            Q(username__iexact=username) | Q(email__iexact=username)
        ).exists():
            raise forms.ValidationError(
                "Este nombre de usuario o correo ya está en uso."
            )

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(
            Q(email__iexact=email) | Q(username__iexact=email)
        ).exists():
            raise forms.ValidationError(
                "Este correo o nombre de usuario ya está en uso."
            )

        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        # A user can only log in after proving they control the email address.
        user.is_active = False

        if commit:
            user.save()

        return user


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Correo electrónico o nombre de usuario",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "username",
                "autocapitalize": "none",
            }
        ),
    )

class ResendPasswordResetForm(PasswordResetForm):
    def send_mail(
            self,
            subject_tempalte_name,
            email_template_name,
            context,
            from_email,
            to_email,
            html_email_template_name=None,
    ):
        reset_url = (
            f"{context['protocol']}://{context['domain']}"
            + reverse(
                "accounts:password_reset_confirm",
                kwargs={
                    "uidb64": context["uid"],
                    "token": context["token"],
                },
            )
        )

        send_password_reset_email(
            email=to_email,
            reset_url=reset_url,
        )
