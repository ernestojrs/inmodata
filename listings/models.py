from django.db import models
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

# Create your models here.

class Listing(models.Model):
    class Source(models.TextChoices):
        DEMO = "demo", "Datos de demostración"
        MANUAL = "manual", "Carga manual o autorizada"
        SUPERCASAS = "supercasas","Supercasas"

    class PropertyType(models.TextChoices):
        APARTMENT = "apartment","Apartamento"

    class OperationType(models.TextChoices):
        SALE = "sale","Venta"

    class Currency(models.TextChoices):
        USD = "USD", "US Dollar"
        DOP = "DOP", "Peso Dominicano"

    source = models.CharField(max_length=30, choices=Source.choices, default=Source.SUPERCASAS)

    source_listing_id = models.CharField(max_length=50)
    source_url = models.URLField(max_length=500)
    property_type = models.CharField(max_length=30, choices=PropertyType.choices, default=PropertyType.APARTMENT)
    operation_type = models.CharField(max_length=30, choices=OperationType.choices, default=OperationType.SALE)
    sector = models.CharField(max_length=100)
    city = models.CharField(max_length=100, default="Santo Domingo")
    price = models.DecimalField(max_digits=14, decimal_places=2, null = True, blank=True, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.USD)
    area_m2 = models.DecimalField(max_digits=10, decimal_places=2, null = True, blank=True, default=Decimal("0.00"))
    bedrooms = models.PositiveSmallIntegerField(null = True, blank=True, default=0)
    bathrooms = models.DecimalField(max_digits = 4, decimal_places=1, null = True, blank=True, default=Decimal("0.0"))
    parking_spaces = models.PositiveSmallIntegerField(null = True, blank=True, default=0)
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['source', 'source_listing_id'], name='unique_source_listing_id')
        ]

        indexes = [
            models.Index(fields=["sector","property_type", "operation_type"]),
            models.Index(fields=["is_active", "last_seen_at"])
        ]
        ordering = ['-last_seen_at']

    def __str__(self):
        return f"{self.get_property_type_display()} en {self.sector} - {self.source_listing_id}"

    @property
    def price_per_m2(self):
        if self.price is not None and self.area_m2 is not None and self.area_m2 > 0:
            return self.price / self.area_m2
        return None

    @property
    def is_stale(self):
        if not self.last_seen_at:
            return True

        stale_date = timezone.now() - timedelta(days=settings.LISTING_STALE_AFTER_DAYS)
        return self.last_seen_at < stale_date

    @property
    def freshness_label(self):
        if self.is_stale:
            return "Datos pendientes de actualización"
        return "Datos Actualizados"

    @property
    def is_stale(self):
        stale_after = timezone.now() - timedelta(days=settings.LISTING_STALE_AFTER_DAYS)
        return self.last_seen_at < stale_after

class ListingPriceSnapshot(models.Model):
    listing = models.ForeignKey(
        Listing,
        on_delete = models.CASCADE,
        related_name= "price_history"
    )

    price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=3,
        choices= Listing.Currency.choices,
    )

    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["listing", "recorded_at"])
        ]

    def __str__(self):
        return f"{self.listing.source_listing_id} - {self.currency} {self.price}"

    


