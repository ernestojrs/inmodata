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
        self.assertContains(response, "Ver bajas de alquiler")
        self.assertContains(
            response,
            reverse("market:rental_price_drops"),
        )
        self.assertContains(response, "Comparar alquileres")
        self.assertContains(
            response,
            reverse("listings:rental_compare"),
        )

        self.assertContains(
            response,
            "Ver oportunidades de alquiler",
        )
        self.assertContains(
            response,
            reverse("market:rental_opportunities"),
        )

        self.assertContains(
            response,
            "Menor alquiler mensual por m²",
        )
        self.assertContains(
            response,
            "Más alquileres registrados",
        )

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


class RentalSectorDetailViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rental-sector-user",
            email="rental-sector@example.com",
            password="SecurePass123!",
        )

        for listing_id, price in (
            ("RENT-SECTOR-NACO-001", "900.00"),
            ("RENT-SECTOR-NACO-002", "1000.00"),
            ("RENT-SECTOR-NACO-003", "1100.00"),
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
            source_listing_id="SALE-SECTOR-NACO-001",
            source_url="https://example.com/sale-sector-naco-001",
            sector="Naco",
            city="Santo Domingo",
            operation_type=Listing.OperationType.SALE,
            price=Decimal("300000.00"),
            area_m2=Decimal("100.00"),
            bedrooms=3,
        )

        SectorMarketSnapshot.objects.create(
            city="Santo Domingo",
            sector="Naco",
            operation_type=Listing.OperationType.RENT,
            snapshot_date=date(2026, 10, 12),
            listings_count=3,
            median_price_per_m2=Decimal("9.00"),
        )

        SectorMarketSnapshot.objects.create(
            city="Santo Domingo",
            sector="Naco",
            operation_type=Listing.OperationType.RENT,
            snapshot_date=date(2026, 10, 13),
            listings_count=3,
            median_price_per_m2=Decimal("10.00"),
        )

        SectorMarketSnapshot.objects.create(
            city="Santo Domingo",
            sector="Naco",
            operation_type=Listing.OperationType.SALE,
            snapshot_date=date(2026, 10, 14),
            listings_count=1,
            median_price_per_m2=Decimal("3000.00"),
        )

    def test_anonymous_user_is_redirected_from_rental_sector_report(self):
        url = reverse(
            "market:rental_sector_detail",
            args=["Naco"],
        )

        response = self.client.get(url)

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={url}",
            fetch_redirect_response=False,
        )

    def test_signed_in_user_sees_rental_sector_metrics_only(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "market:rental_sector_detail",
                args=["Naco"],
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alquileres en Naco")
        self.assertContains(response, "Alquiler mensual promedio")
        self.assertContains(
            response,
            "Alquiler mensual mediano por m²",
        )
        self.assertContains(
            response,
            "Menor alquiler mensual por m²",
        )
        self.assertContains(
            response,
            "Mayor alquiler mensual por m²",
        )

        self.assertEqual(response.context["listings_count"], 3)
        self.assertEqual(
            response.context["average_price"],
            Decimal("1000.00"),
        )
        self.assertEqual(
            response.context["median_price_per_m2"],
            Decimal("10.00"),
        )
        self.assertEqual(
            response.context["lowest_price_per_m2"],
            Decimal("9.00"),
        )
        self.assertEqual(
            response.context["highest_price_per_m2"],
            Decimal("11.00"),
        )
        self.assertEqual(
            response.context["sector_trend"]["difference_percent"],
            Decimal("11.11"),
        )

        self.assertNotContains(response, "300000")


class RentalPriceDropsViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rental-drops-user",
            email="rental-drops@example.com",
            password="SecurePass123!",
        )

        self.rental_listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="RENT-DROP-001",
            source_url="https://example.com/rent-drop-001",
            sector="Naco",
            city="Santo Domingo",
            operation_type=Listing.OperationType.RENT,
            price=Decimal("1000.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
        )

        ListingPriceSnapshot.objects.create(
            listing=self.rental_listing,
            price=Decimal("1200.00"),
            currency=Listing.Currency.USD,
        )

        ListingPriceSnapshot.objects.create(
            listing=self.rental_listing,
            price=Decimal("1000.00"),
            currency=Listing.Currency.USD,
        )

        sale_listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="SALE-DROP-001",
            source_url="https://example.com/sale-drop-001",
            sector="Naco",
            city="Santo Domingo",
            operation_type=Listing.OperationType.SALE,
            price=Decimal("250000.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
        )

        ListingPriceSnapshot.objects.create(
            listing=sale_listing,
            price=Decimal("300000.00"),
            currency=Listing.Currency.USD,
        )

        ListingPriceSnapshot.objects.create(
            listing=sale_listing,
            price=Decimal("250000.00"),
            currency=Listing.Currency.USD,
        )

    def test_anonymous_user_is_redirected_from_rental_price_drops(self):
        url = reverse("market:rental_price_drops")

        response = self.client.get(url)

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={url}",
            fetch_redirect_response=False,
        )

    def test_signed_in_user_sees_rental_reductions_only(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("market:rental_price_drops"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.context["is_rental_price_drops"]
        )
        self.assertContains(
            response,
            "Alquileres con bajas mensuales",
        )
        self.assertContains(response, "Alquiler anterior")
        self.assertContains(response, "Alquiler actual")

        drops = response.context["price_drops"]

        self.assertEqual(len(drops), 1)
        self.assertEqual(
            drops[0]["listing"],
            self.rental_listing,
        )
        self.assertEqual(
            drops[0]["amount"],
            Decimal("200.00"),
        )
        self.assertEqual(
            drops[0]["percent"],
            Decimal("16.67"),
        )

        self.assertNotContains(response, "250000")


class RentalOpportunitiesViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rental-opportunities-user",
            email="rental-opportunities@example.com",
            password="SecurePass123!",
        )

        self.below_market_rental = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="RENT-OPPORTUNITY-001",
            source_url="https://example.com/rent-opportunity-001",
            sector="Naco",
            city="Santo Domingo",
            operation_type=Listing.OperationType.RENT,
            price=Decimal("900.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
        )

        for listing_id, price in (
            ("RENT-OPPORTUNITY-002", "1000.00"),
            ("RENT-OPPORTUNITY-003", "1100.00"),
            ("RENT-OPPORTUNITY-004", "1200.00"),
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
            source_listing_id="SALE-OPPORTUNITY-001",
            source_url="https://example.com/sale-opportunity-001",
            sector="Naco",
            city="Santo Domingo",
            operation_type=Listing.OperationType.SALE,
            price=Decimal("250000.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
        )

    def test_anonymous_user_is_redirected_from_rental_opportunities(self):
        url = reverse("market:rental_opportunities")

        response = self.client.get(url)

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={url}",
            fetch_redirect_response=False,
        )

    def test_signed_in_user_sees_below_market_rentals_only(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("market:rental_opportunities"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.context["is_rental_opportunities"]
        )
        self.assertContains(
            response,
            "Alquileres por debajo del mercado",
        )
        self.assertContains(
            response,
            "Alquiler mensual por m²",
        )

        opportunities = response.context["opportunities"]

        self.assertEqual(len(opportunities), 1)
        self.assertEqual(
            opportunities[0]["listing"],
            self.below_market_rental,
        )
        self.assertEqual(
            opportunities[0]["market_price_per_m2"],
            Decimal("11.00"),
        )
        self.assertEqual(
            opportunities[0]["difference_percent"],
            Decimal("-18.18"),
        )
        self.assertEqual(
            opportunities[0]["comparables_count"],
            3,
        )

        self.assertNotContains(response, "250000")

class SectorBenchmarkDisplayTests(TestCase):
    """Protect the current sector-versus-city values shown to members."""

    def setUp(self):
        """Create distinct Naco and citywide price-per-square-meter medians."""
        self.user = get_user_model().objects.create_user(
            username="benchmark-user",
            password="SecurePass123!",
        )

        Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="BENCHMARK-NACO-001",
            source_url="https://example.com/benchmark-naco-001",
            sector="Naco",
            city="Santo Domingo",
            price=Decimal("200000.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
        )

        for number in range(1, 4):
            Listing.objects.create(
                source=Listing.Source.MANUAL,
                source_listing_id=f"BENCHMARK-PIANTINI-{number}",
                source_url=(
                    f"https://example.com/benchmark-piantini-{number}"
                ),
                sector="Piantini",
                city="Santo Domingo",
                price=Decimal("300000.00"),
                area_m2=Decimal("100.00"),
                bedrooms=2,
            )

    def test_benchmark_keeps_sector_and_city_values_independent(self):
        """Show correct benchmark values even when no trend snapshot exists."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("market:sector_detail", args=["Naco"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            response.context["sector_trend"]["has_comparison"]
        )
        self.assertEqual(
            response.context["sector_benchmark"][
                "sector_median_price_per_m2"
            ],
            Decimal("2000.00"),
        )
        self.assertEqual(
            response.context["sector_benchmark"][
                "city_median_price_per_m2"
            ],
            Decimal("3000.00"),
        )
        self.assertContains(response, "US$ 2000 / m²")
        self.assertContains(response, "US$ 3000 / m²")     

    

class SectorComparisonViewTests(TestCase):
    """Cover member-only sale and rental sector comparisons."""

    def setUp(self):
        """Create distinct active sale and rental samples for two sectors."""
        self.user = get_user_model().objects.create_user(
            username="sector-comparison-user",
            email="sector-comparison@example.com",
            password="SecurePass123!",
        )

        self._create_listing(
            "COMPARE-SALE-NACO-001",
            "Naco",
            Listing.OperationType.SALE,
            "200000.00",
            "100.00",
        )
        self._create_listing(
            "COMPARE-SALE-NACO-002",
            "Naco",
            Listing.OperationType.SALE,
            "240000.00",
            "120.00",
        )
        self._create_listing(
            "COMPARE-SALE-PIANTINI-001",
            "Piantini",
            Listing.OperationType.SALE,
            "360000.00",
            "100.00",
        )
        self._create_listing(
            "COMPARE-SALE-PIANTINI-002",
            "Piantini",
            Listing.OperationType.SALE,
            "330000.00",
            "100.00",
        )
        self._create_listing(
            "COMPARE-SALE-ONLY-001",
            "Venta Exclusiva",
            Listing.OperationType.SALE,
            "180000.00",
            "100.00",
        )
        self._create_listing(
            "COMPARE-RENT-NACO-001",
            "Naco",
            Listing.OperationType.RENT,
            "1800.00",
            "100.00",
        )
        self._create_listing(
            "COMPARE-RENT-PIANTINI-001",
            "Piantini",
            Listing.OperationType.RENT,
            "3000.00",
            "100.00",
        )
        self._create_listing(
            "COMPARE-RENT-ONLY-001",
            "Alquiler Exclusivo",
            Listing.OperationType.RENT,
            "900.00",
            "90.00",
        )

    def _create_listing(
        self,
        identifier,
        sector,
        operation_type,
        price,
        area_m2,
    ):
        """Create one active USD apartment fixture for a market operation."""
        return Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id=identifier,
            source_url=f"https://example.com/{identifier.lower()}",
            property_type=Listing.PropertyType.APARTMENT,
            operation_type=operation_type,
            sector=sector,
            city="Santo Domingo",
            price=Decimal(price),
            currency=Listing.Currency.USD,
            area_m2=Decimal(area_m2),
            bedrooms=2,
            is_active=True,
        )

    def test_anonymous_user_is_redirected_from_sale_sector_comparison(self):
        """Require an account before exposing sale sector comparison data."""
        url = reverse("market:compare_sectors")

        response = self.client.get(url)

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={url}",
            fetch_redirect_response=False,
        )

    def test_signed_in_user_compares_sale_sectors_without_rental_data(self):
        """Use sale-only values and identify the lower median sale sector."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("market:compare_sectors"),
            {
                "sector_1": "Naco",
                "sector_2": "Piantini",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            response.context["is_rental_sector_comparison"]
        )
        self.assertEqual(
            response.context["first_sector_metrics"][
                "median_price_per_m2"
            ],
            Decimal("2000.00"),
        )
        self.assertEqual(
            response.context["comparison"]["lower_median_sector"],
            "Naco",
        )
        self.assertNotIn(
            "Alquiler Exclusivo",
            response.context["available_sectors"],
        )
        self.assertContains(
            response,
            "Naco tiene el menor precio mediano por m².",
        )

        self.assertContains(
            response,
            "SectorComparisonCompleted",
        )
        self.assertContains(
            response,
            "sector_comparison_completed",
        )
        self.assertContains(
            response,
            'market_operation: "sale"',
        )

    def test_anonymous_user_is_redirected_from_rental_sector_comparison(self):
        """Require an account before exposing rental sector comparison data."""
        url = reverse("market:rental_compare_sectors")

        response = self.client.get(url)

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={url}",
            fetch_redirect_response=False,
        )

    def test_signed_in_user_compares_rental_sectors_without_sale_data(self):
        """Use monthly-rental values only on the rental comparison route."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("market:rental_compare_sectors"),
            {
                "sector_1": "Naco",
                "sector_2": "Piantini",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.context["is_rental_sector_comparison"]
        )
        self.assertEqual(
            response.context["first_sector_metrics"][
                "median_price_per_m2"
            ],
            Decimal("18.00"),
        )
        self.assertEqual(
            response.context["comparison"]["lower_median_sector"],
            "Naco",
        )
        self.assertNotIn(
            "Venta Exclusiva",
            response.context["available_sectors"],
        )
        self.assertContains(response, "Alquiler mensual promedio")

        self.assertContains(
            response,
            "RentalSectorComparisonCompleted",
        )
        self.assertContains(
            response,
            "rental_sector_comparison_completed",
        )
        self.assertContains(
            response,
            'market_operation: "rent"',
        )

    def test_same_sector_selection_shows_a_clear_error(self):
        """Prevent a member from comparing one sector with itself."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("market:compare_sectors"),
            {
                "sector_1": "Naco",
                "sector_2": "Naco",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Selecciona dos sectores diferentes.",
        )
        self.assertIsNone(response.context["comparison"])

        self.assertNotContains(
            response,
            "SectorComparisonCompleted",
        )

    def test_sale_comparison_rejects_a_rental_only_sector(self):
        """Reject sectors unavailable in the current sale-data scope."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("market:compare_sectors"),
            {
                "sector_1": "Naco",
                "sector_2": "Alquiler Exclusivo",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Uno de los sectores seleccionados ya no tiene "
            "datos disponibles.",
        )

    def test_member_can_start_sale_comparison_from_sector_report(self):
        """Prefill the sale comparison with the report sector for members."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("market:sector_detail", args=["Naco"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f"{reverse('market:compare_sectors')}?sector_1=Naco",
        )

    def test_member_can_start_rental_comparison_from_sector_report(self):
        """Prefill the rental comparison with the report sector for members."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("market:rental_sector_detail", args=["Naco"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            (
                f"{reverse('market:rental_compare_sectors')}"
                "?sector_1=Naco"
            ),
        )

    def test_prefilled_sector_waits_for_a_second_selection(self):
        """Opening a report link preselects a sector without an error or conversion."""
        self.client.force_login(self.user)

        for route in ("market:compare_sectors", "market:rental_compare_sectors"):
            with self.subTest(route=route):
                response = self.client.get(reverse(route), {"sector_1": "Naco"})

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["selected_sector_1"], "Naco")
                self.assertEqual(response.context["selected_sector_2"], "")
                self.assertIsNone(response.context["error"])
                self.assertIsNone(response.context["comparison"])
                self.assertNotContains(response, "No se pudo comparar")
                self.assertNotContains(response, "SectorComparisonCompleted")
                self.assertNotContains(response, "sector_comparison_completed")

    def test_comparison_ignores_unpriced_and_out_of_city_listings(self):
        """Only priced local apartments should count toward a sector's metrics."""
        self.client.force_login(self.user)

        self._create_listing(
            "COMPARE-NO-PRICE", "Naco", Listing.OperationType.SALE, "0", "100"
        )
        outside_city = self._create_listing(
            "COMPARE-OTHER-CITY", "Naco", Listing.OperationType.SALE, "900000", "100"
        )
        outside_city.city = "Santiago"
        outside_city.save(update_fields=["city"])

        response = self.client.get(
            reverse("market:compare_sectors"),
            {"sector_1": "Naco", "sector_2": "Piantini"},
        )

        self.assertEqual(response.status_code, 200)
        naco = response.context["first_sector_metrics"]
        self.assertEqual(naco["listings_count"], 2)
        self.assertEqual(naco["average_price"], Decimal("220000.00"))
        # Following the dashboard → report → comparison path must keep the same sample.
        overview = self.client.get(reverse("market:overview"))
        report = self.client.get(reverse("market:sector_detail", args=["Naco"]))

        self.assertEqual(overview.status_code, 200)
        self.assertEqual(report.status_code, 200)

        by_sector = {row["sector"]: row for row in overview.context["sector_stats"]}
        for page, metrics in (("dashboard", by_sector["Naco"]), ("report", report.context)):
            with self.subTest(page=page):
                self.assertEqual(metrics["listings_count"], 2)
                self.assertEqual(metrics["average_price"], Decimal("220000.00"))
        
