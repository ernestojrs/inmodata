from django.test import TestCase
from django.urls import reverse

from .models import Listing


class PublicSaleListingsApiTests(TestCase):
    """Protect the public Android feed's visibility rules and response format."""

    def test_guest_only_receives_active_sales(self):
        """A guest gets sale card data, never rentals or inactive listings."""
        for identifier, operation, active in (
            ("mobile-sale", Listing.OperationType.SALE, True),
            ("mobile-rent", Listing.OperationType.RENT, True),
            ("mobile-inactive", Listing.OperationType.SALE, False),
        ):
            Listing.objects.create(
                source_listing_id=identifier,
                source_url=f"https://example.com/{identifier}",
                sector="Naco",
                city="Santo Domingo",
                operation_type=operation,
                is_active=active,
                price="200000.00",
                area_m2="100.00",
                bedrooms=2,
            )

        response = self.client.get(reverse("api_v1_sale_listings"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        sale = Listing.objects.get(source_listing_id="mobile-sale")

        self.assertEqual(data["count"], 1)
        self.assertEqual([row["id"] for row in data["results"]], [sale.pk])
        self.assertEqual(data["results"][0]["price_per_m2"], "2000.00")
        self.assertIsNone(data["next_page"])

    def test_empty_feed_and_invalid_page(self):
        """Distinguish a valid empty catalog from an invalid page request."""
        url = reverse("api_v1_sale_listings")
        self.assertEqual(
            self.client.get(url).json(),
            {"page": 1, "next_page": None, "count": 0, "results": []},
        )
        self.assertEqual(self.client.get(url, {"page": "abc"}).status_code, 400)

    def test_sector_picker_and_filter_use_the_full_public_catalog(self):
        """Offer sectors beyond page one and paginate only the selected sector."""
        sectors = ["El Millón"] + ["Naco"] * 21 + ["Solo alquiler"]
        for index, sector in enumerate(sectors):
            Listing.objects.create(
                source_listing_id=f"sector-test-{index}",
                source_url=f"https://example.com/sector-test-{index}",
                sector=sector,
                city="Santo Domingo",
                operation_type=(
                    Listing.OperationType.RENT
                    if sector == "Solo alquiler"
                    else Listing.OperationType.SALE
                ),
                price="200000.00",
                area_m2="100.00",
            )

        url = reverse("api_v1_sale_listings")
        first = self.client.get(url, {"include_sectors": "1"}).json()
        self.assertEqual(first["count"], 22)
        self.assertNotIn("El Millón", [row["sector"] for row in first["results"]])
        self.assertCountEqual(first["sectors"], ["El Millón", "Naco"])

        filtered = self.client.get(
            url, {"sector": "El Millón", "include_sectors": "1"}
        ).json()
        self.assertEqual(filtered["count"], 1)
        self.assertEqual([row["sector"] for row in filtered["results"]], ["El Millón"])
        self.assertIsNone(filtered["next_page"])
        self.assertCountEqual(filtered["sectors"], ["El Millón", "Naco"])

        second = self.client.get(url, {"sector": "Naco", "page": 2}).json()
        self.assertEqual(second["count"], 21)
        self.assertEqual([row["sector"] for row in second["results"]], ["Naco"])
        self.assertIsNone(second["next_page"])