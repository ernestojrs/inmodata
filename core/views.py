from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from listings.models import Listing, ImportRun
from django.conf import settings
from django.db.models import Count, Max
from django.utils import timezone
from datetime import timedelta
from django.db import DatabaseError, connection
from django.views.decorators.http import require_GET

# Create your views here.
def home(request):
    return render(request, 'core/home.html')

def methodology(request):
    return render(request, "core/methodology.html")

def privacy(request):
    return render(request, "core/privacy.html")

def terms(request):
    return render(request, "core/terms.html")

def data_status(request):
    freshness_limit = (
        timezone.now() - timedelta(days=settings.LISTING_STALE_AFTER_DAYS)
    )

    listings = Listing.objects.filter(
        is_active=True,
        property_type=Listing.PropertyType.APARTMENT,
        operation_type=Listing.OperationType.SALE,
        currency=Listing.Currency.USD,
        price__gt=0,
        area_m2__gt=0,
    )

    sector_coverage = (
        listings.values("sector")
        .annotate(
            listings_count = Count("id"),
            latest_seen_at = Max("last_seen_at"),
        ).order_by("-listings_count", "sector")
    )

    latest_import = ImportRun.objects.first()

    return render(
        request,
         "core/data_status.html",
        {
            "listings_count": listings.count(),
            "sectors_count": listings.values("sector").distinct().count(),
            "fresh_listings_count": listings.filter(
                last_seen_at__gte=freshness_limit
            ).count(),
            "stale_listings_count": listings.filter(
                last_seen_at__lt=freshness_limit
            ).count(),
            "latest_import": latest_import,
            "sector_coverage": sector_coverage,
            "stale_after_days": settings.LISTING_STALE_AFTER_DAYS,
        },
    )

def sitemap(request):
    listings = Listing.objects.filter(
        is_active = True
    ).only(
        "pk",
        "updated_at",
    )

    market_listings = Listing.objects.filter(
         is_active=True,
        property_type=Listing.PropertyType.APARTMENT,
        operation_type=Listing.OperationType.SALE,
        currency=Listing.Currency.USD,
        price__gt=0,
        area_m2__gt=0,
    )

    sectors = (
          market_listings
        .values_list("sector", flat=True)
        .distinct()
        .order_by("sector")
    )

    
    return render(
        request,
        "core/sitemap.xml",
        {
            "base_url": settings.SITE_URL,
            "listings": listings,
            "sectors": sectors,
        },
        content_type= "application/xml",
    )

def robots_txt(request):
    sitemap_url = f"{settings.SITE_URL}{reverse('sitemap')}"


    return HttpResponse(
        f"User-agent: *\nAllow: /\nSitemap: {sitemap_url}\n",
        content_type="text/plain",
    )

def custom_404(request, exception):
    return render(
        request,
        "404.html",
        status=404,
    )

def custom_500(request):
    return render(
        request,
        "500.html",
        status=500,
    )

@require_GET
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({
            "status": "error",
            "message": "Database connection failed.",
        }, status=500,)

    return JsonResponse({
        "status": "ok"
        
    },status=200,)
        