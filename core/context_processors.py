from django.conf import settings


def tracking_settings(request):
    canonical_url = f"{settings.SITE_URL}{request.path}"

    return {
        "meta_pixel_id": settings.META_PIXEL_ID,
        "google_analytics_id": settings.GOOGLE_ANALYTICS_ID,
        "canonical_url": canonical_url,
        "site_url": settings.SITE_URL,
    }