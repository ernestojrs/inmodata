from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch
from decimal import Decimal
from listings.models import Favorite, Listing, SavedSearch

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

class AccountDashboardTests(TestCase):
    """Verify the personal dashboard only exposes the signed-in user's data."""

    def setUp(self):
        """Create distinct account activity for two users."""
        self.user = get_user_model().objects.create_user(
            username="dashboard-user",
            email="dashboard@example.com",
            password="SecurePass123!",
        )
        self.other_user = get_user_model().objects.create_user(
            username="other-dashboard-user",
            email="other-dashboard@example.com",
            password="SecurePass123!",
        )

        sale_listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="DASHBOARD-SALE-001",
            source_url="https://example.com/dashboard-sale-001",
            sector="Naco",
            city="Santo Domingo",
            price=Decimal("200000.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
        )
        rental_listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="DASHBOARD-RENT-001",
            source_url="https://example.com/dashboard-rent-001",
            sector="Piantini",
            city="Santo Domingo",
            operation_type=Listing.OperationType.RENT,
            price=Decimal("1200.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
        )
        other_listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="DASHBOARD-OTHER-001",
            source_url="https://example.com/dashboard-other-001",
            sector="Bella Vista",
            city="Santo Domingo",
            price=Decimal("300000.00"),
            area_m2=Decimal("120.00"),
            bedrooms=3,
        )

        Favorite.objects.create(
            user=self.user,
            listing=sale_listing,
        )
        Favorite.objects.create(
            user=self.user,
            listing=rental_listing,
        )
        Favorite.objects.create(
            user=self.other_user,
            listing=other_listing,
        )

        SavedSearch.objects.create(
            user=self.user,
            name="Naco en venta",
            query_string="sector=Naco&operation_type=sale",
        )
        SavedSearch.objects.create(
            user=self.user,
            name="Piantini alquiler",
            query_string="sector=Piantini&operation_type=rent",
        )
        SavedSearch.objects.create(
            user=self.other_user,
            name="Búsqueda privada",
            query_string="sector=Bella+Vista&operation_type=sale",
        )

    def test_anonymous_user_is_redirected_from_dashboard(self):
        """Require authentication before showing private account activity."""
        dashboard_url = reverse("accounts:dashboard")

        response = self.client.get(dashboard_url)

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={dashboard_url}",
            fetch_redirect_response=False,
        )

    def test_dashboard_shows_only_the_current_users_activity(self):
        """Show accurate sale/rental counts without exposing another user."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("accounts:dashboard"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["favorite_counts"],
            {
                "total": 2,
                "sales": 1,
                "rentals": 1,
            },
        )
        self.assertEqual(
            response.context["saved_search_counts"],
            {
                "total": 2,
                "sales": 1,
                "rentals": 1,
            },
        )
        self.assertContains(response, "Naco")
        self.assertContains(response, "Piantini")
        self.assertContains(response, "Naco en venta")
        self.assertContains(response, "Piantini alquiler")
        self.assertNotContains(response, "Bella Vista")
        self.assertNotContains(response, "Búsqueda privada")