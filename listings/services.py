from decimal import Decimal
from .models import Listing

def get_comparable_listings(sector, target_area_m2, target_bedrooms=None,currency=Listing.Currency.USD):
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

    similar_size_listings = base_listings.filter(
        area_m2__gte=target_area_m2 * Decimal("0.70"),
        area_m2__lte=target_area_m2 * Decimal("1.30"),
    )

    if target_bedrooms is not None:
        similar_bedroom_listings = similar_size_listings.filter(
            bedrooms=target_bedrooms,
        )

        if similar_bedroom_listings.count() >= 3:
            return (
                similar_bedroom_listings,
                "Comparación ajustada por tamaño y habitaciones.",
            )

    if similar_size_listings.count() >= 3:
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