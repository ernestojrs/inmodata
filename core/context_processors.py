from django.conf import settings


def tracking_settings(request):
    return {
        "meta_pixel_id": settings.META_PIXEL_ID,
    }