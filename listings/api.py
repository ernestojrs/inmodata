from django.core.paginator import InvalidPage, Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import Listing
import re
from decimal import Decimal

@require_GET
def public_sale_listings(request):
    """Return one page of public sale listings for the Android Property Explorer.

    This endpoint never accepts an operation type from the client. Rental
    listings and account-specific data belong to separate, protected endpoints.
    """

    listings = Listing.objects.filter(
        is_active=True,
        city__iexact="Santo Domingo",
        property_type=Listing.PropertyType.APARTMENT,
        operation_type=Listing.OperationType.SALE,
        currency=Listing.Currency.USD,
        price__gt=0,
        area_m2__gt=0,
    ).order_by("-last_seen_at", "-pk")

    # Keep the full public-sale query for the sector picker. A selected sector
    # narrows the cards and count, but must not hide other available sectors.
    eligible_sales = listings
    selected_sector = request.GET.get("sector", "").strip()
    if selected_sector:
        listings = eligible_sales.filter(sector=selected_sector)

    # Apply the USD ceiling to the selected sector's results, not to the
    # sector picker. Prices equal to the buyer's budget are included.
    raw_max_price = request.GET.get("max_price", "").strip()

    if raw_max_price:
        if not re.fullmatch(r"[0-9]{1,12}(?:\.[0-9]{1,2})?", raw_max_price):
            return JsonResponse({"error": "Precio máximo no válido."}, status=400)

        max_price = Decimal(raw_max_price)

        if max_price <=0:
            return JsonResponse({"error": "Precio máximo no válido."}, status=400)
        listings = listings.filter(price__lte=max_price)

    # A positive minimum excludes unknown counts (NULL or 0). Without a
    # minimum, keep those listings available to buyers browsing all sales.
    raw_bedrooms = request.GET.get("bedrooms", "").strip()
    if raw_bedrooms:
        if raw_bedrooms not in {"1", "2", "3", "4"}:
           return JsonResponse({"error": "Mínimo de habitaciones no válido."}, status=400)
        listings = listings.filter(bedrooms__gte=int(raw_bedrooms)) 

    paginator = Paginator(listings, 20)

    try:
        page = paginator.page(request.GET.get("page", "1"))
    except InvalidPage:
        return JsonResponse({"error": "Página no válida."}, status=400)

    # Decimal strings preserve the published amounts for Android's BigDecimal.
    results = [
        {
            "id": listing.pk,
            "sector": listing.sector,
            "city": listing.city,
            "currency": listing.currency,
            "price": f"{listing.price:.2f}",
            "area_m2": f"{listing.area_m2:.2f}",
            "price_per_m2": f"{listing.price_per_m2:.2f}",
            "bedrooms": listing.bedrooms,
        }
        for listing in page
    ]

    payload = {
        "page": page.number,
        "next_page": page.next_page_number() if page.has_next() else None,
        "count": paginator.count,
        "results": results,
    }

    # Older app versions receive the same response as before. The new app
    # requests the picker only when opening or refreshing the first page.
    if request.GET.get("include_sectors") == "1":
        payload["sectors"] = list(
            eligible_sales.exclude(sector="")
            .order_by("sector")
            .values_list("sector", flat=True)
            .distinct()
        )

    return JsonResponse(payload)