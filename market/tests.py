from django.template import response
from django.test import TestCase
from decimal import Decimal
from django.urls import reverse
from listings.models import Listing, ListingPriceSnapshot, SectorMarketSnapshot
from django.contrib.auth import get_user_model
from datetime import date


# Create your tests here.

class ValuationViewTests(TestCase):
    def setUp(self):
        Listing.objects.create(
            source=Listing.Source.DEMO,
            source_listing_id="NACO-001",
            source_url="https://example.com/naco-001",
            sector="Naco",
            price=Decimal("180000.00"),
            area_m2=Decimal("90.00"),
            bedrooms=2,
            bathrooms=Decimal("2.0"),
        )

        Listing.objects.create(
            source=Listing.Source.DEMO,
            source_listing_id="NACO-002",
            source_url="https://example.com/naco-002",
            sector="Naco",
            price=Decimal("250000.00"),
            area_m2=Decimal("125.00"),
            bedrooms=3,
            bathrooms=Decimal("2.5"),
        )

        Listing.objects.create(
            source=Listing.Source.DEMO,
            source_listing_id="NACO-BASE-003",
            source_url="https://example.com/naco-003",
            sector="Naco",
            price=Decimal("200000.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
            bathrooms=Decimal("2.0"),
        )

    def test_signed_in_user_can_view_sector_trend(self):
        user = get_user_model().objects.create_user(
            username="trend-user",
            password="SecurePass123!",
        )

        SectorMarketSnapshot.objects.create(
            city="Santo Domingo",
            sector="Naco",
            snapshot_date=date(2026, 10, 12),
            listings_count=3,
            median_price_per_m2=Decimal("2000.00"),
        )

        SectorMarketSnapshot.objects.create(
            city="Santo Domingo",
            sector="Naco",
            snapshot_date=date(2026, 10, 13),
            listings_count=3,
            median_price_per_m2=Decimal("2200.00"),
        )

        SectorMarketSnapshot.objects.create(
            city="Santo Domingo",
            sector="Naco",
            operation_type=Listing.OperationType.RENT,
            snapshot_date=date(2026, 10, 14),
            listings_count=3,
            median_price_per_m2=Decimal("999.00"),
        )

        self.client.force_login(user)

        response = self.client.get(
            reverse("market:sector_detail", args=["Naco"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.context["sector_trend"]["has_comparison"]
        )
        self.assertEqual(
            response.context["sector_trend"]["difference_percent"],
            Decimal("10.00"),
        )
        self.assertContains(response, "Tendencia del mercado")
        self.assertContains(
            response,
            "Subió frente a la última fotografía",
        )
    
    def test_property_with_market_price_is_within_market_range(self):
        response = self.client.get(
            reverse("market:valuation"),
            {
                "sector": "Naco",
                "price": "200000",
                "area_m2": "100",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dentro del rango de mercado")

    def test_property_above_market_price_is_marked_above_market(self):
        response = self.client.get(
            reverse("market:valuation"),
            {
                "sector": "Naco",
                "price": "250000",
                "area_m2": "100",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Por encima del mercado")

    def test_small_sample_warning_is_shown_when_few_comparables_exist(self):
        response = self.client.get(
            reverse("market:valuation"),
            {
                "sector": "Naco",
                 "price": "200000",
                "area_m2": "100",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Esta muestra es pequeña")

    def test_opportunities_page_shows_property_below_market(self):
        Listing.objects.create(
            source=Listing.Source.DEMO,
            source_listing_id="NACO-003",
            source_url="https://example.com/naco-003",
            sector="Naco",
            price=Decimal("150000.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
            bathrooms=Decimal("2.0"),
        )

        response = self.client.get(
            reverse("market:opportunities"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Oportunidades inmobiliarias")
        self.assertEqual(
        response.context["opportunities"][0]["difference_percent"],
        Decimal("-25.00"),
        )

    def test_mortgage_calculator_returns_a_monthly_payment(self):
        response = self.client.get(
            reverse("market:mortgage"),
            {
                "currency": "USD",
                "price": "100000",
                "down_payment": "20000",
                "annual_rate": "12",
                "years": "20",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["result"]["loan_amount"],
            Decimal("80000"),
        )
        self.assertGreater(
            response.context["result"]["monthly_payment"],
            Decimal("0"),
        )

        self.assertContains(
            response,
            'gtag("event", "mortgage_calculation_completed");',
        )

    def test_price_drops_page_shows_reduced_listing(self):
        listing = Listing.objects.create(
            source=Listing.Source.DEMO,
            source_listing_id="DROP-001",
            source_url="https://example.com/drop-001",
            sector="Naco",
            price=Decimal("190000.00"),
            area_m2=Decimal("100.00"),
        )

        ListingPriceSnapshot.objects.create(
            listing=listing,
            price=Decimal("220000.00"),
            currency=Listing.Currency.USD,
        )

        ListingPriceSnapshot.objects.create(
            listing=listing,
            price=Decimal("190000.00"),
            currency=Listing.Currency.USD,
        )

        response = self.client.get(
            reverse("market:price_drops"),
        )

        self.assertEqual(response.status_code, 200)

        first_drop = response.context["price_drops"][0]

        self.assertEqual(first_drop["listing"], listing)
        self.assertEqual(first_drop["amount"], Decimal("30000.00"))

    def test_sector_detail_page_shows_market_metrics(self):
        response = self.client.get(
            reverse("market:sector_detail", args=["Naco"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["sector"], "Naco")
        self.assertContains(response, "Mercado inmobiliario en Naco")
        self.assertContains(response, "Precio mediano por m²")
        self.assertNotContains(
            response,
            "Posición frente a Santo Domingo",
        )

    def test_signed_in_user_can_view_sector_benchmark(self):
        user = get_user_model().objects.create_user(
            username="ernesto",
            password="SecurePass123!",
        )

        self.client.force_login(user)

        response = self.client.get(
            reverse("market:sector_detail", args=["Naco"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Posición frente a Santo Domingo",
        )
        self.assertContains(
            response,
            "Similar al promedio de Santo Domingo",
        )
                

    def test_market_overview_can_sort_sectors_by_lowest_price_per_m2(self):
        Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="PIANTINI-LOW-001",
            source_url="https://example.com/piantini-low-001",
            sector="Piantini",
            city="Santo Domingo",
            price=Decimal("150000.00"),
            area_m2=Decimal("100.00"),
        )

        response = self.client.get(
            reverse("market:overview"),
            {"sort": "price_per_m2_low"},
        )

        first_sector = response.context["sector_stats"][0]["sector"]

        self.assertEqual(first_sector, "Piantini")

    def test_valuation_prefers_similar_size_and_bedrooms(self):
        Listing.objects.create(
            source=Listing.Source.DEMO,
            source_listing_id="NACO-SIMILAR-001",
            source_url="https://example.com/naco-similar-001",
            sector="Naco",
            price=Decimal("200000"),
            area_m2=Decimal("100"),
            bedrooms=2,
        )

        Listing.objects.create(
            source=Listing.Source.DEMO,
            source_listing_id="NACO-SIMILAR-002",
            source_url="https://example.com/naco-similar-002",
            sector="Naco",
            price=Decimal("205000"),
            area_m2=Decimal("100"),
            bedrooms=2,
        )

        Listing.objects.create(
            source=Listing.Source.DEMO,
            source_listing_id="NACO-SIMILAR-003",
            source_url="https://example.com/naco-similar-003",
            sector="Naco",
            price=Decimal("210000"),
            area_m2=Decimal("105"),
            bedrooms=2,
        )

        Listing.objects.create(
            source=Listing.Source.DEMO,
            source_listing_id="NACO-LARGE-001",
            source_url="https://example.com/naco-large-001",
            sector="Naco",
            price=Decimal("1000000"),
            area_m2=Decimal("400"),
            bedrooms=4,
        )

        response = self.client.get(
            reverse("market:valuation"),
            {
                "sector": "Naco",
                "price": "200000",
                "area_m2": "100",
                "bedrooms": "2",
            },
        )

        self.assertEqual(response.status_code, 200)

        result = response.context["result"]

        self.assertEqual(result["comparables_count"], 5)

        self.assertEqual(
            result["comparison_note"],
            "Comparación ajustada por tamaño y habitaciones.",
        )

    def test_valuation_requires_three_comparables(self):
        Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="UNIQUE-PIANTINI-001",
            source_url="https://example.com/unique-piantini-001",
            sector="Piantini",
            city="Santo Domingo",
            price=Decimal("300000"),
            area_m2=Decimal("100"),
        )

        response = self.client.get(
            reverse("market:valuation"),
            {
                "sector": "Piantini",
                "price": "310000",
                "area_m2": "100",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Se necesitan al menos 3")
        self.assertIsNone(response.context["result"])


class RentalMarketOverviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rental-market-user",
            email="rentals@example.com",
            password="SecurePass123!",
        )

        Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="RENT-NACO-001",
            source_url="https://example.com/rent-naco-001",
            sector="Naco",
            city="Santo Domingo",
            operation_type=Listing.OperationType.RENT,
            price=Decimal("1500.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
        )

        Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="RENT-PIANTINI-001",
            source_url="https://example.com/rent-piantini-001",
            sector="Piantini",
            city="Santo Domingo",
            operation_type=Listing.OperationType.RENT,
            price=Decimal("3000.00"),
            area_m2=Decimal("150.00"),
            bedrooms=3,
        )

        Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="SALE-NACO-001",
            source_url="https://example.com/sale-naco-001",
            sector="Naco",
            city="Santo Domingo",
            operation_type=Listing.OperationType.SALE,
            price=Decimal("250000.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
        )

    def test_anonymous_user_is_redirected_from_rental_market(self):
        response = self.client.get(
            reverse("market:rental_overview"),
        )

        self.assertRedirects(
            response,
            (
                f"{reverse('accounts:login')}"
                f"?next={reverse('market:rental_overview')}"
            ),
            fetch_redirect_response=False,
        )

    def test_signed_in_user_sees_only_rental_market_data(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("market:rental_overview"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mercado de alquileres")
        self.assertContains(
            response,
            "Alquiler mensual promedio",
        )
        self.assertEqual(
            response.context["total_listings"],
            2,
        )
        self.assertNotContains(response, "250000")
        self.assertContains(response, "Valorar un alquiler")
        self.assertContains(response, "Calcular rentabilidad")

class RentalValuationViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rental-valuation-user",
            email="rental-valuation@example.com",
            password="SecurePass123!",
        )

        for listing_id, price in (
            ("RENT-NACO-VALUATION-001", "1500.00"),
            ("RENT-NACO-VALUATION-002", "1800.00"),
            ("RENT-NACO-VALUATION-003", "2100.00"),
        ):
            Listing.objects.create(
                source=Listing.Source.MANUAL,
                source_listing_id=listing_id,
                source_url=f"https://example.com/{listing_id}",
                sector="Naco",
                city="Santo Domingo",
                operation_type=Listing.OperationType.RENT,
                price=Decimal(price),
                area_m2=Decimal("100.00"),
                bedrooms=2,
            )

        Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="SALE-NACO-VALUATION-001",
            source_url="https://example.com/sale-naco-valuation-001",
            sector="Naco",
            city="Santo Domingo",
            operation_type=Listing.OperationType.SALE,
            price=Decimal("300000.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
        )

    def test_anonymous_user_is_redirected_from_rental_valuation(self):
        response = self.client.get(
            reverse("market:rental_valuation"),
        )

        self.assertRedirects(
            response,
            (
                f"{reverse('accounts:login')}"
                f"?next={reverse('market:rental_valuation')}"
            ),
            fetch_redirect_response=False,
        )

    def test_signed_in_user_can_value_a_monthly_rent(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("market:rental_valuation"),
            {
                "sector": "Naco",
                "price": "1800",
                "area_m2": "100",
                "bedrooms": "2",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "¿El alquiler mensual es justo?")
        self.assertContains(response, "Dentro del rango de mercado")
        self.assertContains(response, "RentalValuationCompleted")

        result = response.context["result"]

        self.assertEqual(
            result["market_price_per_m2"],
            Decimal("18.00"),
        )
        self.assertEqual(
            result["difference_percent"],
            Decimal("0.00"),
        )


class RentalYieldViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rental-yield-user",
            email="rental-yield@example.com",
            password="SecurePass123!",
        )

        for listing_id, price in (
            ("SALE-YIELD-001", "180000.00"),
            ("SALE-YIELD-002", "200000.00"),
            ("SALE-YIELD-003", "220000.00"),
        ):
            Listing.objects.create(
                source=Listing.Source.MANUAL,
                source_listing_id=listing_id,
                source_url=f"https://example.com/{listing_id}",
                sector="Naco",
                city="Santo Domingo",
                operation_type=Listing.OperationType.SALE,
                price=Decimal(price),
                area_m2=Decimal("100.00"),
                bedrooms=2,
            )

        for listing_id, price in (
            ("RENT-YIELD-001", "900.00"),
            ("RENT-YIELD-002", "1000.00"),
            ("RENT-YIELD-003", "1100.00"),
        ):
            Listing.objects.create(
                source=Listing.Source.MANUAL,
                source_listing_id=listing_id,
                source_url=f"https://example.com/{listing_id}",
                sector="Naco",
                city="Santo Domingo",
                operation_type=Listing.OperationType.RENT,
                price=Decimal(price),
                area_m2=Decimal("100.00"),
                bedrooms=2,
            )

    def test_anonymous_user_is_redirected_from_rental_yield(self):
        response = self.client.get(
            reverse("market:rental_yield"),
        )

        self.assertRedirects(
            response,
            (
                f"{reverse('accounts:login')}"
                f"?next={reverse('market:rental_yield')}"
            ),
            fetch_redirect_response=False,
        )

    def test_signed_in_user_can_calculate_rental_yield(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("market:rental_yield"),
            {
                "sector": "Naco",
                "purchase_price": "200000",
                "monthly_rent": "1000",
                "area_m2": "100",
                "bedrooms": "2",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "¿Qué rentabilidad puede generar?")
        self.assertContains(response, "RentalYieldCalculated")

        result = response.context["result"]

        self.assertEqual(
            result["gross_yield_percent"],
            Decimal("6.00"),
        )
        self.assertEqual(
            result["market_gross_yield_percent"],
            Decimal("6.00"),
        )
        self.assertEqual(
            result["difference_percent"],
            Decimal("0.00"),
        )

        

    
