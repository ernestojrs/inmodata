from decimal import Decimal
from .models import Listing

MINIMUM_COMPARABLES = 3

def get_comparable_listings(sector, target_area_m2, target_bedrooms=None,currency=Listing.Currency.USD,
                            exclude_listing_id=None):
    base_listings = Listing.objects.filter(
         is_active=True,
        property_type=Listing.PropertyType.APARTMENT,
        operation_type=Listing.OperationType.SALE,
        currency=currency,
        price__isnull=False,
        area_m2__isnull=False,
        area_m2__gt=0,
        sector=sector,
    )

    if exclude_listing_id is not None:
        base_listings = base_listings.exclude(pk=exclude_listing_id)



    similar_size_listings = base_listings.filter(
        area_m2__gte=target_area_m2 * Decimal("0.70"),
        area_m2__lte=target_area_m2 * Decimal("1.30"),
    )

    if target_bedrooms is not None:
        similar_bedroom_listings = similar_size_listings.filter(
            bedrooms=target_bedrooms,
        )

        if similar_bedroom_listings.count() >= MINIMUM_COMPARABLES:
            return (
                similar_bedroom_listings,
                "Comparación ajustada por tamaño y habitaciones.",
            )

    if similar_size_listings.count() >= MINIMUM_COMPARABLES:
        return (
            similar_size_listings,
            "Comparación ajustada por tamaño.",
        )

    return (
        base_listings,
        (
            "No hay suficientes propiedades de tamaño similar; "
            "se utilizó el sector completo."
        ),
    )