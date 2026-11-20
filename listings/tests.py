from django.test import TestCase
from io import StringIO
from decimal import Decimal
from pathlib import Path
from .models import (
    Favorite,
    ImportRun,
    Listing,
    ListingPriceSnapshot,
    SavedSearch,
)
from tempfile import TemporaryDirectory
from django.urls import reverse
from django.core.management import call_command
from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from .services import get_comparable_listings
from django.utils import timezone
import csv
import json
from django.contrib.auth import get_user_model

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
        self.assertContains(response, "Compartir por WhatsApp")
        self.assertContains(response, "https://wa.me/")

    def test_detail_page_has_property_structured_data(self):
        listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="SCHEMA-001",
            source_url="https://example.com/schema-001",
            sector="Naco",
            city="Santo Domingo",
            price=Decimal("250000.00"),
            area_m2=Decimal("120.00"),
            bedrooms=3,
            bathrooms=Decimal("2.5"),
        )

        response = self.client.get(
            reverse("listings:detail", args=[listing.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '"@type": "Apartment"')
        self.assertContains(response, '"priceCurrency": "USD"')
        self.assertContains(response, '"name": "Apartamento en Naco"')

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

    def test_rental_price_change_creates_second_price_snapshot(self):
        with TemporaryDirectory() as temporary_directory:
            csv_path = Path(temporary_directory) / "rentals.csv"

            csv_path.write_text(
                (
                    "source,source_listing_id,source_url,property_type,"
                    "operation_type,sector,city,price,currency,area_m2,"
                    "bedrooms,bathrooms,parking_spaces,is_active\n"
                    "manual,RENT-HISTORY-001,"
                    "https://example.com/rent-history-001,"
                    "apartment,rent,Naco,Santo Domingo,1200,USD,100,"
                    "2,2,1,true\n"
                ),
                encoding="utf-8",
            )

            call_command(
                "import_listings_csv",
                str(csv_path),
            )

            csv_path.write_text(
                (
                    "source,source_listing_id,source_url,property_type,"
                    "operation_type,sector,city,price,currency,area_m2,"
                    "bedrooms,bathrooms,parking_spaces,is_active\n"
                    "manual,RENT-HISTORY-001,"
                    "https://example.com/rent-history-001,"
                    "apartment,rent,Naco,Santo Domingo,1000,USD,100,"
                    "2,2,1,true\n"
                ),
                encoding="utf-8",
            )

            call_command(
                "import_listings_csv",
                str(csv_path),
            )

        listing = Listing.objects.get(
            source_listing_id="RENT-HISTORY-001",
        )

        self.assertEqual(
            listing.operation_type,
            Listing.OperationType.RENT,
        )
        self.assertEqual(listing.price, Decimal("1000.00"))

        prices = list(
            listing.price_history.order_by("pk").values_list(
                "price",
                flat=True,
            )
        )

        self.assertEqual(
            prices,
            [
                Decimal("1200.00"),
                Decimal("1000.00"),
            ],
        )

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

class CsvExportViewTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        user_model = get_user_model()

        self.staff_user = user_model.objects.create_superuser(
            username="export-admin",
            email="export@example.com",
            password="secure-password",
        )

        self.normal_user = user_model.objects.create_user(
            username="normal-user",
            password="secure-password",
        )

        Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="EXPORT-001",
            source_url="https://example.com/export-001",
            sector="Naco",
            city="Santo Domingo",
            price=Decimal("200000.00"),
            area_m2=Decimal("100.00"),
        )

    def test_staff_user_can_download_listings_csv(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("listings:export_csv"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response["Content-Type"].startswith("text/csv"),
        )
        self.assertIn(
            "attachment;",
            response["Content-Disposition"],
        )

        csv_text = response.content.decode("utf-8-sig")

        self.assertIn("source_listing_id", csv_text)
        self.assertIn("EXPORT-001", csv_text)

    def test_non_staff_user_cannot_download_listings_csv(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(
            reverse("listings:export_csv"),
        )

        self.assertEqual(response.status_code, 302)

    def test_csv_export_contains_all_listings(self):
        Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="EXPORT-002",
            source_url="https://example.com/export-002",
            sector="Piantini",
            city="Santo Domingo",
            price=Decimal("350000.00"),
            area_m2=Decimal("150.00"),
        )

        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("listings:export_csv"),
        )

        csv_text = response.content.decode("utf-8-sig")
        rows = list(csv.DictReader(StringIO(csv_text)))

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {row["source_listing_id"] for row in rows},
            {"EXPORT-001", "EXPORT-002"},
        )

    def test_staff_user_can_download_full_listings_backup(self):
        listing = Listing.objects.get(
            source_listing_id="EXPORT-001",
        )

        ListingPriceSnapshot.objects.create(
            listing=listing,
            price=Decimal("200000.00"),
            currency=Listing.Currency.USD,
        )

        ImportRun.objects.create(
            sources="manual",
            file_name="backup-test.csv",
            created_count=1,
        )

        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("listings:export_backup"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response["Content-Type"].startswith("application/json"),
        )
        self.assertIn(
            "attachment;",
            response["Content-Disposition"],
        )

        backup_data = json.loads(
            response.content.decode("utf-8"),
        )

        exported_models = {
            item["model"]
            for item in backup_data
        }

        self.assertIn("listings.listing", exported_models)
        self.assertIn(
            "listings.listingpricesnapshot",
            exported_models,
        )
        self.assertIn("listings.importrun", exported_models)

class FavoritesViewTests(TestCase):
    def setUp(self):
        """Create a user plus sale and rental listings for favorite tests."""
        from django.contrib.auth import get_user_model

        user_model = get_user_model()

        self.user = user_model.objects.create_user(
            username="favorite-user",
            email="favorite@example.com",
            password="secure-password",
        )

        self.listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="FAVORITE-001",
            source_url="https://example.com/favorite-001",
            sector="Naco",
            city="Santo Domingo",
            price=Decimal("200000.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
            bathrooms=2,
            is_active=True,
        )

        self.rental_listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="FAVORITE-RENT-001",
            source_url="https://example.com/favorite-rent-001",
            sector="Piantini",
            city="Santo Domingo",
            operation_type=Listing.OperationType.RENT,
            price=Decimal("1200.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
            bathrooms=2,
            is_active=True,
        )

        self.second_rental_listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="FAVORITE-RENT-002",
            source_url="https://example.com/favorite-rent-002",
            sector="Evaristo Morales",
            city="Santo Domingo",
            operation_type=Listing.OperationType.RENT,
            price=Decimal("1400.00"),
            area_m2=Decimal("110.00"),
            bedrooms=2,
            bathrooms=2,
            is_active=True,
        )

        

    def test_anonymous_user_is_redirected_from_favorites_page(self):
        response = self.client.get(
            reverse("listings:favorites"),
        )

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('listings:favorites')}",
            fetch_redirect_response=False,
        )

    def test_signed_in_user_can_view_own_favorites(self):
        Favorite.objects.create(
            user=self.user,
            listing=self.listing,
        )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse("listings:favorites"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mis favoritos")
        self.assertContains(response, "Naco")
        self.assertContains(response, "200000")

    def test_signed_in_user_can_add_and_remove_favorite(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "listings:toggle_favorite",
                args=[self.listing.pk],
            ),
            {
                "next": reverse("listings:favorites"),
            },
        )

        self.assertRedirects(
            response,
            reverse("listings:favorites"),
        )

        self.assertTrue(
            Favorite.objects.filter(
                user=self.user,
                listing=self.listing,
            ).exists()
        )

        self.client.post(
            reverse(
                "listings:toggle_favorite",
                args=[self.listing.pk],
            ),
            {
                "next": reverse("listings:favorites"),
            },
        )

        self.assertFalse(
            Favorite.objects.filter(
                user=self.user,
                listing=self.listing,
            ).exists()
        )

    def test_adding_favorite_stores_tracking_event(self):
        self.client.force_login(self.user)

        self.client.post(
            reverse(
                "listings:toggle_favorite",
                args=[self.listing.pk],
            ),
            {
                "next": reverse("listings:favorites"),
            },
        )

        favorite_event = self.client.session["favorite_event"]

        self.assertEqual(favorite_event["action"], "added")
        self.assertEqual(
            favorite_event["listing_id"],
            self.listing.pk,
        )
        self.assertEqual(
            favorite_event["sector"],
            "Naco",
        )

    def test_rental_filter_shows_only_monthly_rent_favorites(self):
        """Keep rental favorites separate from saved purchase listings."""
        Favorite.objects.create(
            user=self.user,
            listing=self.listing,
        )
        Favorite.objects.create(
            user=self.user,
            listing=self.rental_listing,
        )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse("listings:favorites"),
            {"operation_type": Listing.OperationType.RENT},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["selected_operation_type"],
            Listing.OperationType.RENT,
        )
        self.assertEqual(response.context["favorites"].count(), 1)
        self.assertContains(response, "Piantini")
        self.assertContains(response, "Alquiler mensual")
        self.assertContains(response, "US$ 1200 / mes")
        self.assertNotContains(response, "Naco")

    def test_rental_favorite_shows_verified_change_since_saved(self):
        """Show a rental reduction only when snapshots bracket the save date."""
        favorite = Favorite.objects.create(
            user=self.user,
            listing=self.rental_listing,
        )

        baseline_snapshot = ListingPriceSnapshot.objects.create(
            listing=self.rental_listing,
            price=Decimal("1200.00"),
            currency=Listing.Currency.USD,
        )
        latest_snapshot = ListingPriceSnapshot.objects.create(
            listing=self.rental_listing,
            price=Decimal("1000.00"),
            currency=Listing.Currency.USD,
        )

        ListingPriceSnapshot.objects.filter(
            pk=baseline_snapshot.pk,
        ).update(
            recorded_at=favorite.created_at - timedelta(days=1),
        )
        ListingPriceSnapshot.objects.filter(
            pk=latest_snapshot.pk,
        ).update(
            recorded_at=favorite.created_at + timedelta(days=1),
        )

        self.rental_listing.price = Decimal("1000.00")
        self.rental_listing.save(update_fields=["price"])

        self.client.force_login(self.user)

        response = self.client.get(
            reverse("listings:favorites"),
            {"operation_type": Listing.OperationType.RENT},
        )

        favorite_from_context = next(
            item
            for item in response.context["favorites"]
            if item.pk == favorite.pk
        )
        price_change = favorite_from_context.price_change_since_saved

        self.assertEqual(
            price_change["label"],
            "Alquiler mensual reducido desde que lo guardaste",
        )
        self.assertEqual(
            price_change["amount"],
            Decimal("200.00"),
        )
        self.assertEqual(
            price_change["percent"],
            Decimal("16.67"),
        )
        self.assertContains(response, "US$ 200 / mes")

    def test_user_can_compare_two_rental_favorites(self):
        """Redirect two owned rental favorites to the rental comparator."""
        first_favorite = Favorite.objects.create(
            user=self.user,
            listing=self.rental_listing,
        )
        second_favorite = Favorite.objects.create(
            user=self.user,
            listing=self.second_rental_listing,
        )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse("listings:compare_favorites"),
            {
                "operation_type": Listing.OperationType.RENT,
                "favorite_id": [
                    first_favorite.pk,
                    second_favorite.pk,
                ],
            },
        )

        expected_url = (
            f"{reverse('listings:rental_compare')}"
            f"?listing_1={self.rental_listing.pk}"
            f"&listing_2={self.second_rental_listing.pk}"
        )

        self.assertRedirects(
            response,
            expected_url,
            fetch_redirect_response=False,
        )

    def test_mixed_favorites_cannot_be_compared(self):
        """Reject a selection that combines a sale and a rental favorite."""
        sale_favorite = Favorite.objects.create(
            user=self.user,
            listing=self.listing,
        )
        rental_favorite = Favorite.objects.create(
            user=self.user,
            listing=self.rental_listing,
        )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse("listings:compare_favorites"),
            {
                "operation_type": Listing.OperationType.SALE,
                "favorite_id": [
                    sale_favorite.pk,
                    rental_favorite.pk,
                ],
            },
            follow=True,
        )

        self.assertRedirects(
            response,
            (
                f"{reverse('listings:favorites')}"
                f"?operation_type={Listing.OperationType.SALE}"
            ),
        )
        self.assertContains(
            response,
            "Selecciona dos favoritos del mismo tipo.",
        )

class SavedSearchViewTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        user_model = get_user_model()

        self.user = user_model.objects.create_user(
            username="search-user",
            email="search@example.com",
            password="secure-password",
        )

        self.other_user = user_model.objects.create_user(
            username="other-search-user",
            email="other-search@example.com",
            password="secure-password",
        )

    def test_anonymous_user_is_redirected_from_saved_searches(self):
        response = self.client.get(
            reverse("listings:saved_searches"),
        )

        self.assertRedirects(
            response,
            (
                f"{reverse('accounts:login')}"
                f"?next={reverse('listings:saved_searches')}"
            ),
            fetch_redirect_response=False,
        )

    def test_signed_in_user_can_save_a_filtered_search(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("listings:save_search"),
            {
                "name": "Naco hasta US$250k",
                "sector": "Naco",
                "max_price": "250000",
            },
        )

        self.assertEqual(response.status_code, 302)

        saved_search = SavedSearch.objects.get(
            user=self.user,
            name="Naco hasta US$250k",
        )

        self.assertEqual(
            saved_search.query_string,
            "sector=Naco&max_price=250000&operation_type=sale",
        )

    def test_signed_in_user_can_save_a_rental_search(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("listings:save_search"),
            {
                "name": "Naco alquiler hasta US$1200",
                "sector": "Naco",
                "max_price": "1200",
                "operation_type": Listing.OperationType.RENT,
            },
        )

        saved_search = SavedSearch.objects.get(
            user=self.user,
            name="Naco alquiler hasta US$1200",
        )

        self.assertRedirects(
            response,
            (
                f"{reverse('listings:rentals')}"
                f"?{saved_search.query_string}"
            ),
            fetch_redirect_response=False,
        )
        self.assertIn(
            "operation_type=rent",
            saved_search.query_string,
        )
        self.assertIn(
            "sector=Naco",
            saved_search.query_string,
        )
        self.assertIn(
            "max_price=1200",
            saved_search.query_string,
        )

        response = self.client.get(
            reverse("listings:saved_searches"),
        )

        self.assertEqual(response.status_code, 200)

        saved_search_from_context = next(
            item
            for item in response.context["saved_searches"]
            if item.pk == saved_search.pk
        )

        self.assertEqual(
            saved_search_from_context.catalog_url,
            reverse("listings:rentals"),
        )

    def test_operation_type_alone_does_not_save_a_search(self):
        self.client.force_login(self.user)

        self.client.post(
            reverse("listings:save_search"),
            {
                "name": "No debe guardarse",
                "operation_type": Listing.OperationType.RENT,
            },
        )

        self.assertFalse(
            SavedSearch.objects.filter(
                user=self.user,
                name="No debe guardarse",
            ).exists()
        )

    def test_user_only_sees_own_saved_searches(self):
        SavedSearch.objects.create(
            user=self.user,
            name="Mi búsqueda",
            query_string="sector=Naco",
        )

        SavedSearch.objects.create(
            user=self.other_user,
            name="Búsqueda privada",
            query_string="sector=Piantini",
        )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse("listings:saved_searches"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mi búsqueda")
        self.assertNotContains(response, "Búsqueda privada")

    def test_user_can_delete_own_saved_search(self):
        saved_search = SavedSearch.objects.create(
            user=self.user,
            name="Para eliminar",
            query_string="sector=Naco",
        )

        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "listings:delete_saved_search",
                args=[saved_search.pk],
            ),
        )

        self.assertRedirects(
            response,
            reverse("listings:saved_searches"),
        )

        self.assertFalse(
            SavedSearch.objects.filter(pk=saved_search.pk).exists()
        )

    def test_user_cannot_delete_another_users_saved_search(self):
        saved_search = SavedSearch.objects.create(
            user=self.other_user,
            name="No me pertenece",
            query_string="sector=Piantini",
        )

        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "listings:delete_saved_search",
                args=[saved_search.pk],
            ),
        )

        self.assertEqual(response.status_code, 404)

        self.assertTrue(
            SavedSearch.objects.filter(pk=saved_search.pk).exists()
        )

    def test_rental_saved_search_shows_type_and_filter_summary(self):
        """Show rental metadata without storing duplicate presentation fields."""
        saved_search = SavedSearch.objects.create(
            user=self.user,
            name="Naco alquiler familiar",
            query_string=(
                "sector=Naco&bedrooms=2&max_price=1200&"
                "min_area_m2=80&max_area_m2=120&operation_type=rent"
            ),
        )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse("listings:saved_searches"),
        )

        saved_search_from_context = next(
            item
            for item in response.context["saved_searches"]
            if item.pk == saved_search.pk
        )

        self.assertEqual(
            saved_search_from_context.operation_label,
            "Alquiler mensual",
        )
        self.assertTrue(saved_search_from_context.is_rental)
        self.assertEqual(
            saved_search_from_context.filters_summary,
            (
                "Sector: Naco · 2+ hab. · Hasta US$ 1,200 / mes "
                "· Área: 80–120 m²"
            ),
        )
        self.assertEqual(
            saved_search_from_context.catalog_url,
            reverse("listings:rentals"),
        )
class RentalListingAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rental-detail-user",
            email="rental-detail@example.com",
            password="SecurePass123!",
        )

        self.rental_listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="RENT-DETAIL-001",
            source_url="https://example.com/rent-detail-001",
            sector="Naco",
            city="Santo Domingo",
            operation_type=Listing.OperationType.RENT,
            price=Decimal("1800.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
        )

        self.sale_listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="SALE-DETAIL-001",
            source_url="https://example.com/sale-detail-001",
            sector="Naco",
            city="Santo Domingo",
            operation_type=Listing.OperationType.SALE,
            price=Decimal("250000.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
        )

    def test_anonymous_user_is_redirected_from_rental_detail(self):
        detail_url = reverse(
            "listings:detail",
            args=[self.rental_listing.pk],
        )

        response = self.client.get(detail_url)

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={detail_url}",
            fetch_redirect_response=False,
        )

    def test_signed_in_user_can_view_rental_detail(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "listings:detail",
                args=[self.rental_listing.pk],
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alquiler mensual")
        self.assertContains(response, "← Volver a alquileres")

    def test_anonymous_user_can_still_view_sale_detail(self):
        response = self.client.get(
            reverse(
                "listings:detail",
                args=[self.sale_listing.pk],
            ),
        )

        self.assertEqual(response.status_code, 200)


class RentalComparisonViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rental-comparison-user",
            email="rental-comparison@example.com",
            password="SecurePass123!",
        )

        self.first_rental = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="RENT-COMPARE-001",
            source_url="https://example.com/rent-compare-001",
            sector="Naco",
            city="Santo Domingo",
            operation_type=Listing.OperationType.RENT,
            price=Decimal("900.00"),
            area_m2=Decimal("90.00"),
            bedrooms=2,
        )

        self.second_rental = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="RENT-COMPARE-002",
            source_url="https://example.com/rent-compare-002",
            sector="Piantini",
            city="Santo Domingo",
            operation_type=Listing.OperationType.RENT,
            price=Decimal("1100.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
        )

        self.sale_listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="SALE-COMPARE-001",
            source_url="https://example.com/sale-compare-001",
            sector="Naco",
            city="Santo Domingo",
            operation_type=Listing.OperationType.SALE,
            price=Decimal("250000.00"),
            area_m2=Decimal("100.00"),
            bedrooms=2,
        )

    def test_anonymous_user_is_redirected_from_rental_comparison(self):
        url = reverse("listings:rental_compare")

        response = self.client.get(url)

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={url}",
            fetch_redirect_response=False,
        )

    def test_signed_in_user_can_compare_rentals_only(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("listings:rental_compare"),
            {
                "listing_1": self.first_rental.pk,
                "listing_2": self.second_rental.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_rental_comparison"])
        self.assertEqual(
            response.context["listing_1"],
            self.first_rental,
        )
        self.assertEqual(
            response.context["listing_2"],
            self.second_rental,
        )
        self.assertEqual(
            response.context["comparison"]["lower_price_listing"],
            self.first_rental,
        )
        self.assertContains(response, "Compara dos alquileres")
        self.assertContains(response, "Alquiler mensual")
        self.assertContains(
            response,
            'gtag("event", "rental_comparison_completed");',
        )
        self.assertNotContains(response, "250000")

    def test_sale_listing_cannot_be_compared_on_rental_page(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("listings:rental_compare"),
            {
                "listing_1": self.first_rental.pk,
                "listing_2": self.sale_listing.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Uno de los alquileres seleccionados no está disponible.",
        )
        self.assertIsNone(response.context["listing_2"])

