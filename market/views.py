from django.shortcuts import render
from django.db.models import Avg,DecimalField,Count, F, ExpressionWrapper, Max
from listings.models import Listing
from decimal import Decimal, InvalidOperation
from statistics import mean, median
from django.http import Http404
from listings.services import get_comparable_listings, MINIMUM_COMPARABLES
import json

# Create your views here.



def market_overview(request):
    price_per_m2_expression = ExpressionWrapper(
        F('price') / F('area_m2'),
        output_field=DecimalField(max_digits=14, decimal_places=2)
    )

    listings =( Listing.objects.filter(
        is_active=True,
        property_type= Listing.PropertyType.APARTMENT,
        operation_type= Listing.OperationType.SALE,
        currency= Listing.Currency.USD,
        price__isnull=False,
        area_m2__isnull=False,
        area_m2__gt=0,
        ).annotate(price_per_m2=price_per_m2_expression)
    )

    last_updated = listings.aggregate(latest=Max("last_seen_at"))["latest"]

    selected_sort = request.GET.get(
        "sort",
        "price_per_m2_low",
    )

    sort_options = {
        "price_per_m2_low": "average_price_per_m2",
        "price_per_m2_high": "-average_price_per_m2",
        "most_listings": "-listings_count",
        "sector_name": "sector",
    }

    if selected_sort not in sort_options:
        selected_sort = "price_per_m2_low"

    sector_stats = (
        listings.values("sector")
        .annotate(
            listings_count=Count("id"),
            average_price=Avg("price"),
            average_price_per_m2=Avg("price_per_m2"),
            last_updated = Max("last_seen_at"),
        ).order_by(sort_options[selected_sort])
    )

    context = {
        "total_listings": listings.count(),
        "last_updated" : last_updated,
        "sector_stats": sector_stats,
        "selected_sort": selected_sort,
        "sectors_count": listings.values("sector").distinct().count(),
    }

    return render(request,"market/overview.html", context)

def valuation(request):
    sectors = (
        Listing.objects.filter(
            is_active=True,
            property_type=Listing.PropertyType.APARTMENT,
            operation_type=Listing.OperationType.SALE,
            currency=Listing.Currency.USD,
        ).values_list("sector", flat=True).distinct().order_by("sector")
    )

    selected_sector = request.GET.get("sector", "")
    entered_price = request.GET.get("price", "")
    entered_area_m2 = request.GET.get("area_m2", "")
    entered_bedrooms = request.GET.get("bedrooms","")

    result = None
    error = None

    if selected_sector or entered_price or entered_area_m2 or entered_bedrooms:
        if not selected_sector or not entered_price or not entered_area_m2:
            error = "completa el sector, el precio y el area para evaluar la propiedad."
        else:
            try:
                price = Decimal(entered_price)
                area_m2 = Decimal(entered_area_m2)
                bedrooms = None

                if entered_bedrooms:
                    bedrooms = int(entered_bedrooms)

                if price <=0 or area_m2 <=0 or (bedrooms is not None and bedrooms <0):
                    error = "El precio y el area deben ser mayores a cero."
                else:
                    comparables, comparison_note = get_comparable_listings(
                        selected_sector,
                        area_m2,
                        bedrooms,
                    )
                    comparable_prices_per_m2 = [
                        listing.price_per_m2 for listing in comparables if listing.price_per_m2 is not None
                    ]
                    if len(comparable_prices_per_m2)< MINIMUM_COMPARABLES:
                        error = ("No hay suficientes propiedades comparables en el sector "
                                "seleccionado. Se necesitan al menos 3 propiedades activas.")
                    else:
                        market_price_per_m2 = median(comparable_prices_per_m2)
                        entered_price_per_m2 = (
                            price / area_m2
                            ).quantize(Decimal("0.01"))

                        difference_percent = (
                            (entered_price_per_m2 - market_price_per_m2)/ market_price_per_m2 * Decimal("100")
                        ).quantize(Decimal("0.01"))

                        estimated_market_price =(
                            market_price_per_m2 * area_m2
                        ).quantize(Decimal("0.01"))

                        if difference_percent <= Decimal("-10"):
                            label = "Por debajo del mercado"
                            label_class = "below-market"
                        elif difference_percent <= Decimal("10"):
                            label = "Dentro del rango de mercado"
                            label_class = "within-market"
                        else:
                            label = "Por encima del mercado"
                            label_class = "above-market"

                        result = {
                            "sector": selected_sector,
                            "comparables_count": len(comparable_prices_per_m2),
                            "entered_price" : price,
                            "entered_area_m2" : area_m2,
                            "entered_price_per_m2" : entered_price_per_m2,
                            "market_price_per_m2" : market_price_per_m2,
                            "estimated_market_price" : estimated_market_price,
                            "difference_percent" : difference_percent,
                            "label" : label,
                            "label_class" : label_class,
                            "last_updated" : comparables.aggregate(
                                latest=Max("last_seen_at")
                            )["latest"],
                            "sample_is_small" : len(comparable_prices_per_m2) < 5,
                            "comparison_note": comparison_note,
                        }

            except (InvalidOperation, ValueError):
                error = "Ingresa numeros validos para el precio y el area."

    return render(
        request,
        "market/valuation.html",
        {
            "sectors": sectors,
            "selected_sector": selected_sector,
            "entered_price": entered_price,
            "entered_area_m2": entered_area_m2,
            "result": result,
            "error": error,
            "entered_bedrooms": entered_bedrooms,
        }
    )


def opportunities(request):
    listings = Listing.objects.filter(
        is_active = True,
        property_type = Listing.PropertyType.APARTMENT,
        operation_type = Listing.OperationType.SALE,
        currency = Listing.Currency.USD,
        price__isnull = False,
        area_m2__isnull = False,
        area_m2__gt = 0,
    )

    
    opportunities_list = []

    for listing in listings:
        bedrooms = listing.bedrooms or None

        comparables, comparison_note = get_comparable_listings(
            listing.sector,
            listing.area_m2,
            bedrooms,
            exclude_listing_id=listing.pk,
        )

        comparable_prices_per_m2 = [
            comparable.price_per_m2
            for comparable in comparables
            if comparable.price_per_m2 is not None
        ]

        if len(comparable_prices_per_m2) < MINIMUM_COMPARABLES:
            continue

        market_price_per_m2 = median(comparable_prices_per_m2)

        difference_percent = (
            (
            listing.price_per_m2 - market_price_per_m2
        )
        / market_price_per_m2
        * Decimal("100")
        ).quantize(Decimal("0.01"))

        if difference_percent <= Decimal("-10"):
            opportunities_list.append(
                {
                    "listing": listing,
                    "market_price_per_m2": market_price_per_m2,
                    "difference_percent": difference_percent,
                    "comparables_count": len(
                        comparable_prices_per_m2),
                    "comparison_note": comparison_note,  
                }
            )

    opportunities_list.sort(
        key= lambda item: item["difference_percent"],
    )

    return render(
        request,
        "market/opportunities.html",
        {
            "opportunities": opportunities_list,
        },
    )



    

def mortgage_calculator(request):
    entered_price = request.GET.get("price","")
    entered_down_payment = request.GET.get("down_payment","")
    entered_annual_rate = request.GET.get("annual_rate","")
    entered_years = request.GET.get("years","")
    selected_currency = request.GET.get("currency","")

    result = None
    error = None

    if (
        entered_price or entered_down_payment or entered_annual_rate or entered_years
    ):
        if not all(
            [
                entered_price, entered_years,entered_down_payment, entered_annual_rate,
            ]
        ):
            error = "Completa todos los campos para calcular la cuota"

        else:
            try:
                price = Decimal(entered_price)
                down_payment = Decimal(entered_down_payment)
                annual_rate = Decimal(entered_annual_rate)
                years = Decimal(entered_years)

                if price <= 0 or down_payment<0 or annual_rate <0 or years <=0:
                    error = "Ingresa valores validos mayores o iguales a cero."
                elif down_payment >= price:
                    error = "El inicial debe ser meno que el precio de la propiedad"

                else:
                    loan_amount = price - down_payment
                    months = int(years * Decimal("12"))
                    monthly_rate = annual_rate / Decimal("100") / Decimal("12")

                    if monthly_rate == 0:
                        monthly_payment = loan_amount / months
                    else:
                        factor = (Decimal("1") + monthly_rate) ** months

                        monthly_payment = (
                            loan_amount * monthly_rate * factor / (factor - Decimal("1"))
                        )
                    monthly_payment = monthly_payment.quantize(Decimal("0.01"))
                    total_payment = (monthly_payment * months).quantize(Decimal("0.01"))
                    total_interest = (total_payment - loan_amount).quantize(Decimal("0.01"))

                    result = {
                        "currency": selected_currency,
                        "price": price,
                        "down_payment": down_payment,
                        "loan_amount": loan_amount,
                        "annual_rate": annual_rate,
                        "years": years,
                        "months": months,
                        "monthly_payment": monthly_payment,
                        "total_payment": total_payment,
                        "total_interest": total_interest,
                    }

            except:
                error = "Ingresa numeros validos en todo los campos"

    return render(
        request,
        "market/mortgage.html",
        {
            "entered_price": entered_price,
            "entered_down_payment": entered_down_payment,
            "entered_annual_rate": entered_annual_rate,
            "entered_years": entered_years,
            "selected_currency": selected_currency,
            "result": result,
            "error": error,
        },
    )

def price_drops(request):
    listings = (
        Listing.objects.filter(
            is_active = True,
            property_type=Listing.PropertyType.APARTMENT,
            operation_type=Listing.OperationType.SALE,
            currency=Listing.Currency.USD,
            price__isnull=False,
        ).prefetch_related("price_history")
    )

    price_drops_list = []

    for listing in listings:
        history = sorted(
            listing.price_history.all(),
            key=lambda snapshot: (snapshot.recorded_at,snapshot.pk),
        )

        if len(history) < 2:
            continue

        oldest = history[0]
        newest = history[-1]

        amount = newest.price - oldest.price

        if amount >= 0:
            continue

        percent = (
            amount / oldest.price * Decimal("100")
        ).quantize(Decimal("0.01"))

        price_drops_list.append(
            {
                "listing": listing,
                "oldest_price": oldest.price,
                "newest_price": newest.price,
                "amount": abs(amount),
                "percent": percent,
                
            }
        )

    price_drops_list.sort(key=lambda item: item["percent"])

    return render(
        request,
        "market/price_drops.html",
        {
            "price_drops": price_drops_list,
        }
    )

def sector_detail(request,sector):
    listings = list(
        Listing.objects.filter(
            is_active=True,
            property_type=Listing.PropertyType.APARTMENT,
            operation_type=Listing.OperationType.SALE,
            currency=Listing.Currency.USD,
            sector=sector,
            price__isnull=False,
            area_m2__isnull=False,
            area_m2__gt=0,
        ).order_by("price")
    )

    if not listings:
        raise Http404("No hay datos disponibles para este sector.")

    prices_per_m2 = [
        listing.price_per_m2 
        for listing in listings
        if listing.price_per_m2 is not None
    ]

    median_price_per_m2 = median(prices_per_m2)

    opportunities_count = sum(
        1
        for listing in listings
        if listing.price_per_m2 <= median_price_per_m2 * Decimal("0.90")
    )

    last_updated = max(
        listing.last_seen_at 
        for listing in listings
    )

    return render(
        request,
        "market/sector_detail.html",
        {
            "sector": sector,
            "listings": listings[:10],
            "listings_count": len(listings),
            "average_price": mean(listing.price for listing in listings),
            "median_price_per_m2": median_price_per_m2,
            "lowest_price_per_m2": min(prices_per_m2),
            "highest_price_per_m2": max(prices_per_m2),
            "opportunities_count": opportunities_count,
            "last_updated": last_updated,
            "sample_is_small": len(listings) < 5,
        },
    )