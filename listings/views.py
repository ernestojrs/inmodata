from django.shortcuts import render, get_object_or_404
from django.db.models import DecimalField, F, ExpressionWrapper, Max, Q, Prefetch
from .models import Listing, Favorite, SavedSearch, ListingPriceSnapshot
from decimal import Decimal, InvalidOperation
from statistics import mean, median
from django.core.paginator import Paginator
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from django.contrib.admin.views.decorators import staff_member_required
from django.core.management import call_command
from django.core.management.base import CommandError
from .forms import CsvImportForm, SavedSearchForm
from .services import get_comparable_listings, MINIMUM_COMPARABLES
from django.http import HttpResponse, QueryDict
from django.utils import timezone
import csv
import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login


# =============================================================================
# SALE AND RENTAL CATALOG ARCHITECTURE
# =============================================================================
# Catalog, comparison, and saved-search behavior is shared by sale and rental
# listings through the `operation_type` argument.
#
# Sale remains the default for backward compatibility. Rental wrappers require
# authentication and pass RENT explicitly. Saved searches store operation_type
# in their query string so they reopen the correct catalog without duplicating
# data in the database.
#
# When adding a listing feature, always filter by operation_type so sale prices
# and monthly rents cannot appear in the same result set.
# =============================================================================

SAVED_SEARCH_FILTERS = (
    "q",
    "sector",
    "bedrooms",
    "min_price",
    "max_price",
    "min_area_m2",
    "max_area_m2",
    "sort",
    "operation_type",
)


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

def build_saved_search_summary(query_parameters, is_rental):
    """Return a readable summary of filters stored in a saved search.

    SavedSearch stores one encoded query string. This helper converts that
    technical data into display-only text without duplicating database fields.
    """

    summary_parts = []

    monthly_suffix = " / mes" if is_rental else ""
    search_term = query_parameters.get("q", "").strip()
    sector = query_parameters.get("sector", "").strip()
    bedrooms = parse_optional_int(
        query_parameters.get("bedrooms", "")
    )
    min_price = parse_optional_decimal(
        query_parameters.get("min_price", "")
    )
    max_price = parse_optional_decimal(
        query_parameters.get("max_price", "")
    )
    min_area_m2 = parse_optional_decimal(
        query_parameters.get("min_area_m2", "")
    )
    max_area_m2 = parse_optional_decimal(
        query_parameters.get("max_area_m2", "")
    )

    # Ignore malformed values from old or manually edited URLs.
    if min_price is not None and not min_price.is_finite():
        min_price = None
    if max_price is not None and not max_price.is_finite():
        max_price = None
    if min_area_m2 is not None and not min_area_m2.is_finite():
        min_area_m2 = None
    if max_area_m2 is not None and not max_area_m2.is_finite():
        max_area_m2 = None

    if search_term:
        summary_parts.append(f"Buscar: {search_term}")

    if sector:
        summary_parts.append(f"Sector: {sector}")

    if bedrooms is not None and bedrooms > 0:
        summary_parts.append(f"{bedrooms}+ hab.")

    if min_price is not None and max_price is not None:
        summary_parts.append(
            f"US$ {min_price:,.0f}–{max_price:,.0f}{monthly_suffix}"
        )
    elif min_price is not None:
        summary_parts.append(
            f"Desde US$ {min_price:,.0f}{monthly_suffix}"
        )
    elif max_price is not None:
        summary_parts.append(
            f"Hasta US$ {max_price:,.0f}{monthly_suffix}"
        )

    if min_area_m2 is not None and max_area_m2 is not None:
        summary_parts.append(
            f"Área: {min_area_m2:,.0f}–{max_area_m2:,.0f} m²"
        )
    elif min_area_m2 is not None:
        summary_parts.append(f"Desde {min_area_m2:,.0f} m²")
    elif max_area_m2 is not None:
        summary_parts.append(f"Hasta {max_area_m2:,.0f} m²")

    return " · ".join(summary_parts) or "Filtros personalizados"

def listings_list(request,operation_type=Listing.OperationType.SALE):
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
        operation_type=operation_type,
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

    favorite_listing_ids = set()

    if request.user.is_authenticated:
        favorite_listing_ids = set(
            Favorite.objects.filter(
                user=request.user,
                listing__in=page_obj.object_list,
            ).values_list("listing_id", flat=True)
        )

    current_path = request.get_full_path()

    query_parameters = request.GET.copy()
    query_parameters.pop("page",None)
    base_query = query_parameters.urlencode()

    sectors = (
        Listing.objects.filter(
            is_active=True,
            property_type=Listing.PropertyType.APARTMENT,
            operation_type=operation_type,
            currency=Listing.Currency.USD,
        ).values_list("sector", flat=True).distinct().order_by("sector")
    )

    is_rental_catalog = (
        operation_type == Listing.OperationType.RENT
    )

    catalog_url = (
        reverse("listings:rentals")
        if is_rental_catalog
        else reverse("listings:list")
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
        "favorite_listing_ids": favorite_listing_ids,
        "current_path": current_path,
        "saved_search_form": SavedSearchForm(),
                "is_rental_catalog": is_rental_catalog,
        "catalog_url": catalog_url,
        "catalog_page_title": (
            "Apartamentos en alquiler"
            if is_rental_catalog
            else "Propiedades"
        ),
        "catalog_meta_description": (
            "Explora apartamentos activos en alquiler mensual, "
            "filtra por sector, precio, área y habitaciones "
            "en Santo Domingo."
            if is_rental_catalog
            else (
                "Explora apartamentos activos en venta, filtra "
                "por sector, precio, área y habitaciones en "
                "Santo Domingo."
            )
        ),
        "catalog_eyebrow": (
            "Apartamentos en alquiler"
            if is_rental_catalog
            else "Apartamentos en venta"
        ),
        "catalog_heading": (
            "Explorar alquileres"
            if is_rental_catalog
            else "Explorar propiedades"
        ),
        "catalog_lead": (
            "Compara alquiler mensual, tamaño y alquiler mensual "
            "por metro cuadrado."
            if is_rental_catalog
            else (
                "Compara precio, tamaño y precio por metro cuadrado."
            )
        ),
        "catalog_price_label": (
            "Alquiler mensual (US$)"
            if is_rental_catalog
            else "Precio mín. (US$)"
        ),
        "catalog_price_per_m2_label": (
            "Alquiler mensual por m²"
            if is_rental_catalog
            else "Precio por m²"
        ),
        "catalog_price_suffix": (
            " / mes"
            if is_rental_catalog
            else ""
        ),
        "allow_saved_search": True,
        "saved_search_operation_type": operation_type,
    }
    
    return render(request, "listings/list.html", context)



@login_required
def rentals_list(request):
    return listings_list(
        request,
        operation_type=Listing.OperationType.RENT,
    )

@require_POST
@login_required
def save_search(request):
    form = SavedSearchForm(request.POST)

    if not form.is_valid():
        messages.error(
            request,
            "Escribe un nombre válido para guardar la búsqueda.",
        )

        return redirect("listings:list")

    query_parameters = request.POST.copy()

    operation_type = query_parameters.get("operation_type", Listing.OperationType.SALE)

    if operation_type not in Listing.OperationType.values:
        operation_type = Listing.OperationType.SALE

    query_parameters["operation_type"] = operation_type

    for key in list(query_parameters):
        value = query_parameters.get(key,"").strip()

        if key not in SAVED_SEARCH_FILTERS or not value:
            query_parameters.pop(key)

    meaningful_filters = (
        "q",
        "sector",
        "bedrooms",
        "min_price",
        "max_price",
        "min_area_m2",
        "max_area_m2",
       
    )

    if not any(query_parameters.get(key) for key in meaningful_filters):
        messages.error(
            request,
            "Selecciona al menos un filtro antes de guardar la búsqueda.",
        )
        return redirect("listings:list")

    query_string = query_parameters.urlencode()

    saved_search, created = SavedSearch.objects.update_or_create(
        user=request.user,
        name=form.cleaned_data["name"],

        defaults={
            "query_string": query_string,
        },
    )

    if created:
        messages.success(
            request,
            f'Búsqueda "{saved_search.name}" guardada.',
        )
    else:
        messages.info(
            request,
            f'Búsqueda "{saved_search.name}" actualizada.',
        )

    catalog_url = (
        reverse("listings:rentals")
        if operation_type == Listing.OperationType.RENT
        else reverse("listings:list")
    )

    return redirect(f"{catalog_url}?{query_string}")

@login_required
def saved_searches(request):

    """Show readable saved-sale and saved-rental searches for one user.

    Display fields are derived from each stored query string at request time.
    This keeps the query string as the single source of truth and avoids a
    database migration for presentation-only metadata.
    """
    saved_searches = SavedSearch.objects.filter(
        user=request.user,
    )

    for saved_search in saved_searches:
        query_parameters = QueryDict(saved_search.query_string)

        operation_type = query_parameters.get(
            "operation_type",
            Listing.OperationType.SALE,
        )

         # Legacy searches may not include an operation type, so they remain sales.
        if operation_type not in Listing.OperationType.values:
            operation_type = Listing.OperationType.SALE

        is_rental = operation_type == Listing.OperationType.RENT


        saved_search.catalog_url = (
            reverse("listings:rentals")
            if is_rental
            else reverse("listings:list")
        )

        saved_search.operation_label = (
            "Alquiler mensual"
            if is_rental
            else "Precio de venta"
        )

        saved_search.is_rental = is_rental
        saved_search.filters_summary = build_saved_search_summary(
            query_parameters,
            is_rental,
        )

    return render(
        request,
        "listings/saved_searches.html",
        {
            "saved_searches": saved_searches,
        },
    )

@require_POST
@login_required
def delete_saved_search(request,pk):
    saved_search = get_object_or_404(
        SavedSearch,
        pk=pk,
        user=request.user,
    )

    saved_search_name = saved_search.name 
    saved_search.delete()

    messages.success(
        request,
        f'Búsqueda "{saved_search_name}" eliminada.',
    )

    return redirect("listings:saved_searches")


def listing_detail(request, pk):
    listing = get_object_or_404(
        Listing,
        pk=pk,
        is_active = True,
    )

    is_rental_listing = (
        listing.operation_type == Listing.OperationType.RENT
    )

    if (
        is_rental_listing
        and not request.user.is_authenticated
    ):
        return redirect_to_login(request.get_full_path())

    

    is_favorite = False

    if request.user.is_authenticated:
        is_favorite = Favorite.objects.filter(
            user = request.user,
            listing = listing,
        ).exists()

    comparables, comparison_note = get_comparable_listings(
         sector=listing.sector,
        target_area_m2=listing.area_m2,
        target_bedrooms=listing.bedrooms or None,
        currency=listing.currency,
        exclude_listing_id=listing.pk,
        operation_type=listing.operation_type,
    )

    comparable_prices_per_m2 = [
        comparable.price_per_m2
        for comparable in comparables 
        if comparable.price_per_m2 is not None
    ]

    analysis = None

    if listing.price_per_m2 is not None and len(comparable_prices_per_m2) >= MINIMUM_COMPARABLES:
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
            label = (
                "Alquiler reducido"
                if is_rental_listing
                else "Precio reducido"
            )
            label_class = "price-reduced"
        elif amount >0:
            label = (
                "Alquiler aumentado"
                if is_rental_listing
                else "Precio aumentado"
            )
            label_class = "price-increased"
        else:
            label = (
                "Alquiler sin cambios"
                if is_rental_listing
                else "Precio sin cambios"
            )
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

    listing_schema = {
        "@context": "https://schema.org",
        "@type": "Apartment",
        "@id": f"{request.build_absolute_uri()}#apartment",
        "name": f"Apartamento en {listing.sector}",
        "description": (
            f"Apartamento en "
            f"{'alquiler mensual' if is_rental_listing else 'venta'} "
            f"en {listing.sector}, {listing.city}. "
            "Análisis de mercado inmobiliario por InmoData."
        ),
        "url": request.build_absolute_uri(),
        "dateModified": listing.updated_at.isoformat(),
        "address": {
            "@type": "PostalAddress",
            "addressLocality": listing.city,
            "addressCountry": "DO",
        },
        "floorSize": {
            "@type": "QuantitativeValue",
            "value": float(listing.area_m2),
            "unitText": "m²",
        },
        "offers": {
            "@type": "Offer",
            "price": float(listing.price),
            "priceCurrency": listing.currency,
            "url": listing.source_url,
        },
    }

    if listing.bedrooms is not None:
        listing_schema["numberOfBedrooms"] = listing.bedrooms

    if listing.bathrooms is not None:
        listing_schema["numberOfBathroomsTotal"] = float(
            listing.bathrooms
        )

    listing_schema_json = json.dumps(
        listing_schema,
        ensure_ascii=False,
    ).replace("</", "<\\/")

    

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
            "listing_schema_json": listing_schema_json,
            "is_favorite": is_favorite,
            "current_path": request.get_full_path(),
            "is_rental_listing": is_rental_listing,
            "listing_operation_label": (
                "Alquiler mensual"
                if is_rental_listing
                else "Precio de venta"
            ),
            "listing_price_suffix": (
                " / mes"
                if is_rental_listing
                else ""
            ),
            "listing_hero_eyebrow": (
                "Análisis de alquiler"
                if is_rental_listing
                else "Análisis de propiedad"
            ),
            "listing_hero_lead": (
                "Comparación del alquiler mensual de este apartamento "
                "con alquileres activos del mismo sector."
                if is_rental_listing
                else (
                    "Comparación del precio de esta propiedad con apartamentos "
                    "activos del mismo sector."
                )
            ),
            "listing_price_per_m2_label": (
                "Alquiler mensual por m²"
                if is_rental_listing
                else "Precio por m²"
            ),
            "listing_published_per_m2_label": (
                "Alquiler mensual publicado por m²"
                if is_rental_listing
                else "Precio publicado por m²"
            ),
            "listing_market_per_m2_label": (
                "Alquiler mensual de mercado por m²"
                if is_rental_listing
                else "Referencia de mercado por m²"
            ),
            "listing_comparables_label": (
                "alquileres comparables"
                if is_rental_listing
                else "propiedades comparables"
            ),
            "listing_catalog_url": (
                reverse("listings:rentals")
                if is_rental_listing
                else reverse("listings:list")
            ),
            "listing_catalog_label": (
                "← Volver a alquileres"
                if is_rental_listing
                else "← Volver a propiedades"
            ),
        }
    )

def compare_listings(request, operation_type=Listing.OperationType.SALE):

    is_rental_comparison = (
        operation_type == Listing.OperationType.RENT
    )

    available_listings = Listing.objects.filter(
        is_active = True,
         property_type=Listing.PropertyType.APARTMENT,
        operation_type=operation_type,
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
             error = (
                "Selecciona dos alquileres para compararlos."
                if is_rental_comparison
                else "Selecciona dos propiedades para compararlas."
            )
        elif selected_listing_1_id == selected_listing_2_id:
            error = (
                "Selecciona dos alquileres diferentes."
                if is_rental_comparison
                else "Selecciona dos propiedades diferentes."
            )
        else:
            listing_1 = available_listings.filter(
                pk=selected_listing_1_id
            ).first()

            listing_2 = available_listings.filter(
                pk=selected_listing_2_id
            ).first()

            if not listing_1 or not listing_2:
                error = (
                    "Uno de los alquileres seleccionados no está disponible."
                    if is_rental_comparison
                    else (
                        "Una de las propiedades seleccionadas "
                        "no está disponible."
                    )
                )

    comparison = None
    if listing_1 and listing_2:
        price_per_m2_1 = listing_1.price_per_m2
        price_per_m2_2 = listing_2.price_per_m2

        if price_per_m2_1 is not None and price_per_m2_2 is not None:
            if price_per_m2_1 == price_per_m2_2:
                comparison = {
                    "label": (
                        "Los dos alquileres tienen el mismo "
                        "alquiler mensual por m²."
                        if is_rental_comparison
                        else (
                            "Las Dos propiedades tienen el mismo "
                            "precio por m2."
                        )
                    ),
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

                if is_rental_comparison:
                    position = (
                        "primer"
                        if lower_price_listing.pk == listing_1.pk
                        else "segundo"
                    )

                    label = (
                        f"El {position} alquiler tiene el menor "
                        "alquiler mensual por m²."
                    )
                else:

                    position = (
                        "primera"
                        if lower_price_listing.pk == listing_1.pk
                        else "segunda"
                    )
                    label = (
                        f"La {position} propiedad tiene el menor "
                        "precio por m2."
                    )


                comparison = {
                    "label": label,
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
            "is_rental_comparison": is_rental_comparison,
         },
    )

@login_required
def rental_compare_listings(request):
    return compare_listings(
        request,
        operation_type=Listing.OperationType.RENT,
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

@staff_member_required
def export_listings_csv(request):
    timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")

    response = HttpResponse(
        content_type="text/csv; charset=utf-8",
    )

    response["Content-Disposition"] = (
        f"attachment; filename=inmodata_listings_{timestamp}.csv"

    )

    response.write("\ufeff")

    writer = csv.writer(response)

    writer.writerow(
        [
            "source",
            "source_listing_id",
            "source_url",
            "property_type",
            "operation_type",
            "sector",
            "city",
            "price",
            "currency",
            "area_m2",
            "bedrooms",
            "bathrooms",
            "parking_spaces",
            "is_active",
            "first_seen_at",
            "last_seen_at",
        ]
    )

    listings = Listing.objects.all().order_by(
        "source",
        "source_listing_id",
    )

    for listing in listings:
        writer.writerow(
            [
                listing.source,
                listing.source_listing_id,
                listing.source_url,
                listing.property_type,
                listing.operation_type,
                listing.sector,
                listing.city,
                listing.price,
                listing.currency,
                listing.area_m2,
                listing.bedrooms,
                listing.bathrooms,
                listing.parking_spaces,
                listing.is_active,
                listing.first_seen_at.isoformat(),
                listing.last_seen_at.isoformat(),
            ]
        )     

    return response    

@staff_member_required
def export_listings_backup(request):
    timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")

    response = HttpResponse(
        content_type="application/json: charset=utf-8",
    )   

    response["Content-Disposition"] = (
        f"attachment; filename=inmodata_listings_backup_{timestamp}.json"
    )

    call_command(
        "dumpdata",
        "listings",
        indent = 2,
        stdout = response,
    )

    return response


@require_POST
@login_required
def toggle_favorite(request,pk):
    listing = get_object_or_404(
        Listing,
        pk=pk,
        is_active = True
    )

    favorite, created = Favorite.objects.get_or_create(
        user = request.user,
        listing = listing,
    )

    if created:
        request.session["favorite_event"] = {
            "action": "added",
            "listing_id": listing.pk,
            "name": f"Apartamento en {listing.sector}",
            "sector": listing.sector,
        }

        messages.success(
            request,
            "Propiedad guardada en Mis favoritos.",
        )

    else:
        favorite.delete()

        messages.info(
            request,
            "Propiedad eliminada de Mis favoritos.",
        )

    next_url = request.POST.get("next","")

    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse("listings:detail", args=[listing.pk])

    return redirect(next_url)

def get_favorite_price_change(favorite):
     """Return a verified price change that happened after a favorite was saved.

    The comparison uses the last snapshot at or before the favorite date as
    the baseline, then compares it with the newest snapshot. Returning None
    when evidence is incomplete prevents the interface from making guesses.
    """
     price_history = getattr(
        favorite.listing,
        "favorite_price_history",
        [],
     )

     if not price_history:
        return None

     saved_price_snapshot = next(
         (
         snapshot
         for snapshot in reversed(price_history)
         if snapshot.recorded_at <= favorite.created_at
        ),
        None,
    )

     latest_snapshot = price_history[-1]

     if saved_price_snapshot is None:
            return None

     if latest_snapshot.recorded_at <= favorite.created_at:
            return None

     if saved_price_snapshot.currency != latest_snapshot.currency:
            return None

     if saved_price_snapshot.price <= 0:
            return None

     amount = latest_snapshot.price - saved_price_snapshot.price

     if amount == 0:
            return None

     is_rental = (
        favorite.listing.operation_type == Listing.OperationType.RENT
     )

     if amount < 0:
        label = (
            "Alquiler mensual reducido desde que lo guardaste"
            if is_rental
            else "Precio reducido desde que lo guardaste"
        )
        css_class = "favorite-price-change--down"

     else:
        label = (
            "Alquiler mensual aumentado desde que lo guardaste"
            if is_rental
            else "Precio aumentado desde que lo guardaste"
        )
        css_class = "favorite-price-change--up"

     percent = (
         abs(amount)
         / saved_price_snapshot.price
         * Decimal("100")
     ).quantize(Decimal("0.01"))

     return{
        "label": label,
        "css_class": css_class,
        "amount": abs(amount),
        "percent": percent,
     }

@login_required
def favorites_list(request):
    """Show active favorites with sale/rental filters and verified changes.

    Price history is prefetched once for the complete favorite list, avoiding
    one database query per favorite while supporting change indicators.
    """
    selected_operation_type = request.GET.get(
        "operation_type",
        "all",
    )

    valid_operation_types = (
        Listing.OperationType.SALE,
        Listing.OperationType.RENT,
    )

    if selected_operation_type not in valid_operation_types:
        selected_operation_type = "all"

    favorites=(
        Favorite.objects.filter(
            user=request.user,
            listing__is_active=True,
        ).select_related("listing")
        .prefetch_related(
            Prefetch(
                "listing__price_history",
                queryset=ListingPriceSnapshot.objects.only(
                    "id",
                    "listing_id",
                    "price",
                    "currency",
                    "recorded_at",
                ).order_by("recorded_at", "pk"),
                to_attr="favorite_price_history",
            )
        )
    )

    if selected_operation_type != "all":
        favorites = favorites.filter(
            listing__operation_type=selected_operation_type
        )

     # Attach temporary display data; it is not duplicated in the database.
    for favorite in favorites:
        favorite.price_change_since_saved = (
            get_favorite_price_change(favorite)
        )

    return render(
        request,
        "listings/favorites.html",
        {
            "favorites": favorites,
            "selected_operation_type": selected_operation_type,
        },
    )

@login_required
def compare_favorites(request):
    """Redirect two owned favorites to the correct existing comparison page.

    The selection is validated server-side so a user cannot compare another
    user's favorite, inactive listings, mixed sale/rental listings, or fewer
    than exactly two saved favorites.
    """

    selected_operation_type = request.GET.get(
        "operation_type",
        "",
    )

    favorites_url = reverse("listings:favorites")

    if selected_operation_type not in Listing.OperationType.values:
        messages.error(
            request,
            "Selecciona primero Venta o Alquiler mensual.",
        )
        return redirect(favorites_url)
    favorites_url = (
        f"{favorites_url}"
        f"?operation_type={selected_operation_type}"
    )

    try:
        selected_favorite_ids = [
            int(value)
            for value in request.GET.getlist("favorite_id")
        ]
    except (TypeError, ValueError):
        selected_favorite_ids = []

    if(
        len(selected_favorite_ids) != 2
        or len(set(selected_favorite_ids)) != 2
    ):
        messages.error(
            request,
            "Selecciona exactamente dos favoritos para comparar.",
        )
        return redirect(favorites_url)

    favorites_by_id = {
        favorite.pk: favorite
        for favorite in Favorite.objects.filter(
            pk__in=selected_favorite_ids,
            user=request.user,
            listing__is_active=True,
        ).select_related("listing")
    }

    if len(favorites_by_id) != 2:
       messages.error(
            request,
            "Uno de los favoritos seleccionados ya no está disponible.",
        )
       return redirect(favorites_url)

    selected_favorites = [
        favorites_by_id[favorite_id]
        for favorite_id in selected_favorite_ids
    ]

    if any(
        favorite.listing.operation_type != selected_operation_type
        for favorite in selected_favorites
    ):
        messages.error(
            request,
            "Selecciona dos favoritos del mismo tipo.",
        )
        return redirect(favorites_url)

    comparison_url = (
        reverse("listings:rental_compare")
        if selected_operation_type == Listing.OperationType.RENT
        else reverse("listings:compare")
    )

    return redirect(
        f"{comparison_url}"
        f"?listing_1={selected_favorites[0].listing_id}"
        f"&listing_2={selected_favorites[1].listing_id}"
    )
 


