from django.shortcuts import render
from django.http import HttpResponse
from django.urls import reverse
from listings.models import Listing

# Create your views here.
def home(request):
    return render(request, 'core/home.html')

def methodology(request):
    return render(request, "core/methodology.html")

def privacy(request):
    return render(request, "core/privacy.html")

def terms(request):
    return render(request, "core/terms.html")

def sitemap(request):
    listings = Listing.objects.filter(
        is_active = True
    ).only(
        "pk",
        "updated_at",
    )

    base_url = request.build_absolute_uri("/").rstrip("/")

    return render(
        request,
        "core/sitemap.xml",
        {
            "base_url": base_url,
            "listings": listings,
        },
        content_type= "application/xml",
    )

def robots_txt(request):
    sitemap_url = request.build_absolute_uri(
        reverse("sitemap")
    )

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