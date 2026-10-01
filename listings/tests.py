from django.test import TestCase
from io import StringIO
from decimal import Decimal
from pathlib import Path
from .models import Listing, ListingPriceSnapshot, ImportRun
from tempfile import TemporaryDirectory
from django.urls import reverse
from django.core.management import call_command
from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from .services import get_comparable_listings
from django.utils import timezone

# Create your tests here.

class ListingModelTests(TestCase):
    def test_price_per_m2_is_calculated_correctly(self):
        listing = Listing(
            source = Listing.Source.DEMO,
            source_listing_id = "TEST-001",
            source_url = "https://example.com/test-001",
            sector = "Naco",
            price = Decimal("200000.00"),
            area_m2 = Decimal("100.00"),
        )

        self.assertEqual(listing.price_per_m2,Decimal("2000.00"))

    def test_price_per_m2_is_none_when_area_is_missing(self):
        listing = Listing(
            source=Listing.Source.DEMO,
            source_listing_id="TEST-002",
            source_url="https://example.com/test-002",
            sector="Naco",
            price=Decimal("200000.00"),
            area_m2=None,
        )

        self.assertIsNone(listing.price_per_m2)

    def test_listing_is_stale_after_fourteen_days(self):
        listing = Listing(
            source=Listing.Source.DEMO,
            source_listing_id="STALE-001",
            source_url="https://example.com/stale-001",
            sector="Naco",
            price=Decimal("200000.00"),
            area_m2=Decimal("100.00"),
            last_seen_at=timezone.now() - timedelta(days=15),
        )

        self.assertTrue(listing.is_stale)

    def test_listing_is_stale_after_fourteen_days_without_update(self):
        listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="MANUAL-STALE-001",
            sector="Naco",
            city="Santo Domingo",
            price=200000,
            area_m2=100,
            last_seen_at=timezone.now() - timedelta(days=15),
        )

        self.assertTrue(listing.is_stale)
        self.assertEqual(
            listing.freshness_label,
            "Datos pendientes de actualización",
        )

class ComparableListingServiceTests(TestCase):
    def test_prefers_similar_size_and_bedrooms(self):
        for number, area_m2, price in [
            ("001", "95", "190000"),
            ("002", "100", "200000"),
            ("003", "110", "220000"),
        ]:
            Listing.objects.create(
                source=Listing.Source.MANUAL,
                source_listing_id=f"NACO-SIMILAR-{number}",
                source_url=(
                    f"https://example.com/naco-similar-{number}"
                ),
                sector="Naco",
                city="Santo Domingo",
                price=Decimal(price),
                area_m2=Decimal(area_m2),
                bedrooms=2,
            )

        large_listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="NACO-LARGE-001",
            source_url="https://example.com/naco-large-001",
            sector="Naco",
            city="Santo Domingo",
            price=Decimal("1000000"),
            area_m2=Decimal("400"),
            bedrooms=4,
        )

        comparables, comparison_note = get_comparable_listings(
            sector="Naco",
            target_area_m2=Decimal("100"),
            target_bedrooms=2,
        )

        self.assertEqual(comparables.count(), 3)
        self.assertNotIn(large_listing, comparables)

        self.assertEqual(
            comparison_note,
            "Comparación ajustada por tamaño y habitaciones.",
        )

class ListingDetailPriceChangeTests(TestCase):
    def test_price_reduction_is_shown_when_history_has_two_snapshots(self):
        listing = Listing.objects.create(
            source=Listing.Source.DEMO,
            source_listing_id="PRICE-DROP-001",
            source_url="https://example.com/price-drop-001",
            sector="Naco",
            price=Decimal("200000.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
            bathrooms=Decimal("2.0"),
        )

        ListingPriceSnapshot.objects.create(
            listing=listing,
            price=Decimal("220000.00"),
            currency=Listing.Currency.USD,
        )
        ListingPriceSnapshot.objects.create(
            listing=listing,
            price=Decimal("200000.00"),
            currency=Listing.Currency.USD,
        )

        response = self.client.get(reverse("listings:detail", args=[listing.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Precio reducido")

    def test_detail_page_has_whatsapp_share_link(self):
        listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="WHATSAPP-001",
            source_url="https://example.com/whatsapp-001",
            sector="Naco",
            city="Santo Domingo",
            price=Decimal("200000.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
        )

        response = self.client.get(
            reverse("listings:detail", args=[listing.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Compartir análisis por WhatsApp")
        self.assertContains(response, "https://wa.me/")

class ListingFilterTests(TestCase):
    def setUp(self):
        Listing.objects.create(
            source=Listing.Source.DEMO,
            source_listing_id="FILTER-CHEAP",
            source_url="https://example.com/filter-cheap",
            sector="Naco",
            price=Decimal("180000.00"),
            area_m2=Decimal("80.00"),
            bedrooms=2,
        )
        Listing.objects.create(
            source=Listing.Source.DEMO,
            source_listing_id="FILTER-EXPENSIVE",
            source_url="https://example.com/filter-expensive",
            sector="Naco",
            price=Decimal("320000.00"),
            area_m2=Decimal("140.00"),
            bedrooms=3,
        )

    def test_min_price_hides_cheaper_listings(self):
        response = self.client.get(
            reverse("listings:list"),
            {"min_price": "200000"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "320000")
        self.assertNotContains(response, "180000")
        self.assertEqual(response.context["results_count"], 1)

    def test_listings_are_paginated(self):
        for number in range(23):
            Listing.objects.create(
                source=Listing.Source.DEMO,
                source_listing_id=f"PAGE-{number}",
                source_url=f"https://example.com/page-{number}",
                sector="Naco",
                price=Decimal("200000.00"),
                area_m2=Decimal("100.00"),
                bedrooms=2,
            )

        response = self.client.get(
            reverse("listings:list"),
            {"page": "2"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(len(response.context["page_obj"]), 5)

    def test_listings_can_be_sorted_by_highest_price(self):
        response = self.client.get(
            reverse("listings:list"),
            {"sort": "price_high"},
        )

        self.assertEqual(response.status_code, 200)

        first_listing = response.context["page_obj"].object_list[0]

        self.assertEqual(
            first_listing.source_listing_id,
            "FILTER-EXPENSIVE",
        )

    def test_two_listings_can_be_compared(self):
        first_listing = Listing.objects.get(
            source_listing_id="FILTER-CHEAP"
        )
        second_listing = Listing.objects.get(
            source_listing_id="FILTER-EXPENSIVE"
        )

        response = self.client.get(
            reverse("listings:compare"),
            {
                "listing_1": first_listing.pk,
                "listing_2": second_listing.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["listing_1"], first_listing)
        self.assertEqual(response.context["listing_2"], second_listing)
        self.assertContains(
            response,
            'gtag("event", "property_comparison_completed");',
        )

    def test_comparison_identifies_the_listing_with_lower_price_per_m2(self):
        first_listing = Listing.objects.get(
            source_listing_id="FILTER-CHEAP"
        )
        second_listing = Listing.objects.get(
            source_listing_id="FILTER-EXPENSIVE"
        )

        response = self.client.get(
            reverse("listings:compare"),
            {
                "listing_1": first_listing.pk,
                "listing_2": second_listing.pk,
            },
        )

        comparison = response.context["comparison"]

        self.assertEqual(
            comparison["lower_price_listing"],
            first_listing,
        )
        self.assertContains(
            response,
            "La primera propiedad tiene el menor precio por m2.",
        )
    def test_listings_can_be_searched_by_sector(self):
        searched_listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="SEARCH-GAZCUE-001",
            source_url="https://example.com/search-gazcue-001",
            sector="Gazcue",
            city="Santo Domingo",
            price=Decimal("210000.00"),
            area_m2=Decimal("105.00"),
            bedrooms=2,
        )

        response = self.client.get(
            reverse("listings:list"),
            {"q": "gaz"},
        )

        result_ids = [
            listing.pk
            for listing in response.context["page_obj"].object_list
        ]

        self.assertIn(searched_listing.pk, result_ids)
        self.assertEqual(response.context["entered_query"], "gaz")

class SimilarListingsTests(TestCase):
    def test_detail_page_shows_similar_listings_from_the_same_sector(self):
        target_listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="TARGET-001",
            sector="Naco",
            city="Santo Domingo",
            price=Decimal("200000.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
        )

        similar_listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="SIMILAR-001",
            sector="Naco",
            city="Santo Domingo",
            price=Decimal("210000.00"),
            area_m2=Decimal("102.00"),
            bedrooms=2,
        )

        Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="OTHER-SECTOR-001",
            sector="Piantini",
            city="Santo Domingo",
            price=Decimal("210000.00"),
            area_m2=Decimal("102.00"),
            bedrooms=2,
        )

        response = self.client.get(
            reverse("listings:detail", args=[target_listing.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            similar_listing,
            response.context["similar_listings"],
        )
        self.assertContains(response, "Alternativas similares")

class ImportListingsCsvCommandTests(TestCase):
    def test_dry_run_does_not_create_a_listing(self):
        with TemporaryDirectory() as temporary_directory:
            csv_path = Path(temporary_directory) / "listings.csv"

            csv_path.write_text(
                (
                    "source,source_listing_id,source_url,property_type,"
                    "operation_type,sector,city,price,currency,area_m2,"
                    "bedrooms,bathrooms,parking_spaces,is_active\n"
                    "manual,DRY-RUN-001,https://example.com/dry-run-001,"
                    "apartment,sale,Naco,Santo Domingo,200000,USD,100,"
                    "2,2,1,true\n"
                ),
                encoding="utf-8",
            )

            output = StringIO()

            call_command(
                "import_listings_csv",
                str(csv_path),
                "--dry-run",
                stdout=output,
            )

        self.assertFalse(
            Listing.objects.filter(
                source_listing_id="DRY-RUN-001"
            ).exists()
        )

        self.assertEqual(ImportRun.objects.count(), 0)

        self.assertIn(
            "Simulación completada",
            output.getvalue(),
        )

    def test_real_import_creates_listing_and_price_snapshot(self):
        with TemporaryDirectory() as temporary_directory:
            csv_path = Path(temporary_directory) / "listings.csv"

            csv_path.write_text(
                (
                    "source,source_listing_id,source_url,property_type,"
                    "operation_type,sector,city,price,currency,area_m2,"
                    "bedrooms,bathrooms,parking_spaces,is_active\n"
                    "manual,REAL-IMPORT-001,https://example.com/real-001,"
                    "apartment,sale,Naco,Santo Domingo,250000,USD,125,"
                    "3,2,2,true\n"
                ),
                encoding="utf-8",
            )

            call_command(
                "import_listings_csv",
                str(csv_path),
            )

        listing = Listing.objects.get(
            source_listing_id="REAL-IMPORT-001"
        )

        self.assertEqual(listing.price, Decimal("250000"))
        self.assertEqual(listing.area_m2, Decimal("125"))
        self.assertEqual(listing.price_history.count(), 1)

        import_run = ImportRun.objects.get()

        self.assertEqual(import_run.sources, "manual")
        self.assertEqual(import_run.file_name, "listings.csv")
        self.assertEqual(import_run.created_count, 1)
        self.assertEqual(import_run.updated_count, 0)
        self.assertEqual(import_run.skipped_count, 0)

    def test_deactivate_missing_dry_run_keeps_listing_active(self):
        old_listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="OLD-LISTING-001",
            source_url="https://example.com/old-001",
            sector="Naco",
            city="Santo Domingo",
            price=Decimal("200000"),
            area_m2=Decimal("100"),
            last_seen_at=timezone.now() - timedelta(days=30),
            is_active=True,
        )

        with TemporaryDirectory() as temporary_directory:
            csv_path = Path(temporary_directory) / "listings.csv"

            csv_path.write_text(
                (
                    "source,source_listing_id,source_url,property_type,"
                    "operation_type,sector,city,price,currency,area_m2,"
                    "bedrooms,bathrooms,parking_spaces,is_active\n"
                    "manual,CURRENT-LISTING-001,"
                    "https://example.com/current-001,"
                    "apartment,sale,Naco,Santo Domingo,220000,USD,110,"
                    "2,2,1,true\n"
                ),
                encoding="utf-8",
            )

            call_command(
                "import_listings_csv",
                str(csv_path),
                "--dry-run",
                "--deactivate-missing",
            )

        old_listing.refresh_from_db()

        self.assertTrue(old_listing.is_active)

class CsvUploadViewTests(TestCase):
    def test_staff_user_can_simulate_csv_import(self):
        user = self.client.login(
            username="admin",
            password="admin-password",
        )

        if not user:
            from django.contrib.auth import get_user_model

            user_model = get_user_model()

            user_model.objects.create_superuser(
                username="admin",
                email="admin@example.com",
                password="admin-password",
            )

            self.client.login(
                username="admin",
                password="admin-password",
            )

        csv_file = SimpleUploadedFile(
            "listings.csv",
            (
                b"source,source_listing_id,source_url,property_type,"
                b"operation_type,sector,city,price,currency,area_m2,"
                b"bedrooms,bathrooms,parking_spaces,is_active\n"
                b"manual,UPLOAD-001,https://example.com/upload-001,"
                b"apartment,sale,Naco,Santo Domingo,200000,USD,100,"
                b"2,2,1,true\n"
            ),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("listings:import_upload"),
            {
                "csv_file": csv_file,
                "dry_run": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Simulación completada")
        self.assertFalse(
            Listing.objects.filter(
                source_listing_id="UPLOAD-001"
            ).exists()
        )

        