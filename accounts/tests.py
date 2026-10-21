from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from .models import EmailVerification


class AccountViewsTests(TestCase):
    @patch("accounts.views.send_verification_email")
    def test_user_can_create_an_account(self, send_verification_email):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "ernesto",
                "email": "ernesto@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:verification_sent"),
        )

        user = get_user_model().objects.get(username="ernesto")
        self.assertEqual(user.email, "ernesto@example.com")
        self.assertFalse(user.is_active)
        self.assertTrue(EmailVerification.objects.filter(user=user).exists())
        send_verification_email.assert_called_once()

    def test_user_can_log_in(self):
        get_user_model().objects.create_user(
            username="ernesto",
            email="ernesto@example.com",
            password="SecurePass123!",
        )

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "ernesto",
                "password": "SecurePass123!",
            },
        )

        self.assertRedirects(
            response,
            reverse("home"),
        )

    def test_user_can_log_in_with_email(self):
        get_user_model().objects.create_user(
            username="ernesto",
            email="ernesto@example.com",
            password="SecurePass123!",
        )

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "ernesto@example.com",
                "password": "SecurePass123!",
            },
        )

        self.assertRedirects(response, reverse("home"))

    def test_valid_verification_activates_user_and_tracks_once(self):
        user = get_user_model().objects.create_user(
            username="ernesto",
            email="ernesto@example.com",
            password="SecurePass123!",
            is_active=False,
        )
        verification = EmailVerification.objects.create(user=user)

        response = self.client.get(
            reverse(
                "accounts:verify_email",
                kwargs={"token": verification.token},
            )
        )

        self.assertRedirects(
            response,
            reverse("accounts:signup_complete"),
            fetch_redirect_response=False,
        )
        user.refresh_from_db()
        verification.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNotNone(verification.verified_at)

        complete_response = self.client.get(reverse("accounts:signup_complete"))
        self.assertContains(complete_response, '"CompleteRegistration"')
        self.assertContains(complete_response, '"sign_up"')

        refreshed_response = self.client.get(reverse("accounts:signup_complete"))
        self.assertNotContains(refreshed_response, '"CompleteRegistration"')


    @patch("accounts.forms.send_password_reset_email")
    def test_password_reset_sends_email_for_active_user(self, send_email):
        get_user_model().objects.create_user(
            username="ernesto",
            email="ernesto@example.com",
            password="SecurePass123!",
        )

        response = self.client.post(
            reverse("accounts:password_reset"),
            {
                "email": "ernesto@example.com",
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:password_reset_done"),
        )
        send_email.assert_called_once()

        self.assertEqual(
            send_email.call_args.kwargs["email"],
            "ernesto@example.com",
        )

    @patch("accounts.forms.send_password_reset_email")
    def test_password_reset_does_not_reveal_unknown_email(self, send_email):
        response = self.client.post(
            reverse("accounts:password_reset"),
            {
                "email": "unknown@example.com",
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:password_reset_done"),
        )
        send_email.assert_not_called()