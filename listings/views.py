from django.shortcuts import render, get_object_or_404
from django.db.models import DecimalField, F, ExpressionWrapper, Max, Q
from .models import Listing
from decimal import Decimal, InvalidOperation
from statistics import mean, median
from django.core.paginator import Paginator
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from django.contrib.admin.views.decorators import staff_member_required
from django.core.management import call_command
from django.core.management.base import CommandError
from .forms import CsvImportForm
from .services import get_comparable_listings
# Create your views here.

def parse_optional_decimal(value):
    if not value:
        return None
    try:
        return Decimal(value)
    except:
        return None

def parse_optional_int(value):
    if not value:
        return None

    try:
        return int(value)
    except:
        return None



def listings_list(request):
    selected_sector = request.GET.get("sector", "")
    entered_query = request.GET.get("q", "").strip()
    selected_bedrooms = request.GET.get("bedrooms", "")
    entered_min_price = request.GET.get("min_price", "")
    entered_max_price = request.GET.get("max_price", "")
    entered_min_area_m2 = request.GET.get("min_area_m2", "")
    entered_max_area_m2 = request.GET.get("max_area_m2", "")
    selected_sort = request.GET.get("sort", "recent")

    bedrooms = parse_optional_int(selected_bedrooms)
    min_price = parse_optional_decimal(entered_min_price)
    max_price = parse_optional_decimal(entered_max_price)
    min_area_m2 = parse_optional_decimal(entered_min_area_m2)
    max_area_m2 = parse_optional_decimal(entered_max_area_m2)

    price_per_m2_expression = ExpressionWrapper(
        F('price') / F('area_m2'),
        output_field=DecimalField(max_digits=14, decimal_places=2)
    )

    listings = Listing.objects.filter(
        is_active=True,
        property_type=Listing.PropertyType.APARTMENT,
        operation_type=Listing.OperationType.SALE,
        currency=Listing.Currency.USD,
        price__isnull=False,
        area_m2__isnull=False,
        area_m2__gt=0,
    )

    if entered_query:
        listings = listings.filter(
            Q(sector__icontains=entered_query)
            | Q(city__icontains=entered_query)
    )

    if selected_sector:
        listings = listings.filter(sector=selected_sector)

    if bedrooms is not None:
        listings = listings.filter(bedrooms__gte=bedrooms)

    if min_price is not None:
        listings = listings.filter(price__gte=min_price)

    if max_price is not None:
        listings = listings.filter(price__lte=max_price)

    if min_area_m2 is not None:
        listings = listings.filter(area_m2__gte=min_area_m2)

    if max_area_m2 is not None:
        listings = listings.filter(area_m2__lte=max_area_m2)

    sort_options = {
        "recent": "-last_seen_at",
        "price_low": "price",
        "price_high": "-price",
        "price_per_m2_low": "calculated_price_per_m2",
        "price_per_m2_high": "-calculated_price_per_m2",
    }

    if selected_sort not in sort_options:
        selected_sort = "recent"

    listings = listings.annotate(
        calculated_price_per_m2=price_per_m2_expression
    ).order_by(sort_options[selected_sort])

    results_count = listings.count()

    paginator = Paginator(listings,20)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_parameters = request.GET.copy()
    query_parameters.pop("page",None)
    base_query = query_parameters.urlencode()

    sectors = (
        Listing.objects.filter(
            is_active=True,
            property_type=Listing.PropertyType.APARTMENT,
            operation_type=Listing.OperationType.SALE,
            currency=Listing.Currency.USD,
        ).values_list("sector", flat=True).distinct().order_by("sector")
    )

    context = {
        "page_obj": page_obj,
        "base_query": base_query,
        "sectors": sectors,
        "selected_sector": selected_sector,
        "selected_bedrooms": selected_bedrooms,
        "entered_min_price": entered_min_price,
        "entered_max_price": entered_max_price,
        "entered_min_area_m2": entered_min_area_m2,
        "entered_max_area_m2": entered_max_area_m2,
        "selected_sort": selected_sort,
        "entered_query": entered_query,
        "results_count": results_count,
    }
    
    return render(request, "listings/list.html", context)

def listing_detail(request, pk):
    listing = get_object_or_404(
        Listing,
        pk=pk,
        is_active = True,
    )

    comparables, comparison_note = get_comparable_listings(
         sector=listing.sector,
        target_area_m2=listing.area_m2,
        target_bedrooms=listing.bedrooms or None,
        currency=listing.currency,
    )

    comparable_prices_per_m2 = [
        comparable.price_per_m2
        for comparable in comparables 
        if comparable.price_per_m2 is not None
    ]

    analysis = None

    if listing.price_per_m2 is not None and comparable_prices_per_m2:
        market_price_per_m2 = median(comparable_prices_per_m2)

        difference_percent = (
            (listing.price_per_m2 - market_price_per_m2)/ market_price_per_m2 * Decimal(100)
        ).quantize(Decimal('0.01'))

        if difference_percent <= Decimal("-10"):
            label = "Por debajo del mercado"
            label_class = "below-market"
        elif difference_percent <= Decimal("10"):
            label = "Dentro del rango de mercado"
            label_class = "within-market"
        else:
            label = "Por encima del mercado"
            label_class = "above-market"

        last_updated = comparables.aggregate(latest = Max("last_seen_at"))["latest"]
        comparables_count = len(comparable_prices_per_m2)

        analysis = {
            "comparables_count": comparables_count,
            "market_price_per_m2": market_price_per_m2,
            "difference_percent": difference_percent,
            "label": label,
            "label_class": label_class,
            "last_updated" : last_updated,
            "sample_is_small" : comparables_count < 5,
            "comparison_note": comparison_note,
        }

    similar_listings = []

    if listing.price_per_m2 is not None:
        similar_listings = sorted(
            comparables,
            key = lambda comparable:(
                0 if comparable.bedrooms == listing.bedrooms else 1,
                abs(comparable.area_m2 - listing.area_m2),
                abs(comparable.price_per_m2 - listing.price_per_m2),

            ),
        )[:3]

    price_history = list (listing.price_history.all().order_by("recorded_at", "pk") )

    price_change = None

    if len(price_history) >=2:
        oldest = price_history[0]
        newest = price_history[-1]
        amount = newest.price - oldest.price

        if amount < 0:
            label = "Precio reducido"
            label_class = "price-reduced"
        elif amount >0:
            label = "Precio Aumentado"
            label_class = "price-increased"
        else:
            label = "Precio sin cambios"
            label_class = "price-unchanged"

        percent = None

        if oldest.price:
            percent = (amount / oldest.price * Decimal("100")).quantize(Decimal("0.01"))

        price_change = {
            "label": label,
            "label_class": label_class,
            "amount": abs(amount),
            "percent": percent,
        }

    return render(
        request,
        "listings/detail.html",
        {
            "listing": listing,
            "analysis": analysis,
            "price_history": price_history,
            "price_change" : price_change,
            "similar_listings": similar_listings,
            "share_text":(
                f"Revisa este analisis de Inmodata: apartamento en "
                f"{listing.sector}, {listing.currency} {listing.price} \n"
                f"{listing.area_m2} m2.  \n"
                f"{request.build_absolute_uri()}"
            ),
        }
    )

def compare_listings(request):
    available_listings = Listing.objects.filter(
        is_active = True,
         property_type=Listing.PropertyType.APARTMENT,
        operation_type=Listing.OperationType.SALE,
        currency=Listing.Currency.USD,
        price__isnull=False,
        area_m2__isnull=False,
        area_m2__gt=0,
    ).order_by("sector","price")

    selected_listing_1_id = request.GET.get("listing_1", "")
    selected_listing_2_id = request.GET.get("listing_2", "")

    listing_1 = None
    listing_2 = None
    error = None

    if selected_listing_1_id or selected_listing_2_id:
        if not selected_listing_1_id or not selected_listing_2_id:
            error = "Selecciona dos propiedades para compararlas."
        elif selected_listing_1_id == selected_listing_2_id:
            error = "Selecciona dos propiedades diferentes."
        else:
            listing_1 = available_listings.filter(
                pk=selected_listing_1_id
            ).first()

            listing_2 = available_listings.filter(
                pk=selected_listing_2_id
            ).first()

            if not listing_1 or not listing_2:
                error = "Una de las propiedades seleccionadas no está disponible."

    comparison = None
    if listing_1 and listing_2:
        price_per_m2_1 = listing_1.price_per_m2
        price_per_m2_2 = listing_2.price_per_m2

        if price_per_m2_1 is not None and price_per_m2_2 is not None:
            if price_per_m2_1 == price_per_m2_2:
                comparison = {
                    "label": "Las Dos propiedades tienen el mismo precio por m2.",
                    "difference_percent": Decimal("0.00"),
                    "lower_price_listing": None,
                }
            else:
                lower_price_listing = (
                    listing_1
                    if price_per_m2_1 < price_per_m2_2
                    else listing_2
                )

                higher_price_per_m2 = max(price_per_m2_1, price_per_m2_2)
                lower_price_per_m2 = min(price_per_m2_1, price_per_m2_2)

                difference_percent = (
                    (higher_price_per_m2 - lower_price_per_m2)/ higher_price_per_m2 * Decimal("100")

                ).quantize(Decimal("0.01"))

                position = (
                    "primera"
                    if lower_price_listing.pk == listing_1.pk
                    else "segunda"
                )

                comparison = {
                    "label":(
                        f"La {position} propiedad tiene el menor precio por m2."
                    ),
                    "difference_percent": difference_percent,
                    "lower_price_listing": lower_price_listing,
                }

    return render(
        request,
         "listings/compare.html",
          {
            "available_listings": available_listings,
            "selected_listing_1_id": selected_listing_1_id,
            "selected_listing_2_id": selected_listing_2_id,
            "listing_1": listing_1,
            "listing_2": listing_2,
            "error": error,
            "comparison": comparison,
         },
    )

@staff_member_required
def import_listings_upload(request):
    result = None

    if request.method == "POST":
        form = CsvImportForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            uploaded_file = form.cleaned_data["csv_file"]

            command_arguments = []

            if form.cleaned_data["dry_run"]:
                command_arguments.append("--dry-run")

            if form.cleaned_data["deactivate_missing"]:
                command_arguments.append("--deactivate-missing")

            output = StringIO()

            try:
                with TemporaryDirectory() as temporary_directory:
                    csv_path = (
                        Path(temporary_directory) 
                        / Path(uploaded_file.name).name
                    )

                    with csv_path.open("wb") as destination:
                        for chunk in uploaded_file.chunks():
                            destination.write(chunk)

                    call_command(
                        "import_listings_csv",
                        str(csv_path),
                        *command_arguments,
                        stdout = output,
                    )

                result = output.getvalue()

            except CommandError as error:
                form.add_error(None, str(error))

    else:
        form = CsvImportForm()

    return render(
        request,
        "listings/import_upload.html",
        {
            "form": form,
            "result": result,
        }
    )

                
