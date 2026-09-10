from django.urls import path
from . import views
app_name = "listings"

urlpatterns = [
    path("", views.listings_list, name="list"),
    path("comparar/", views.compare_listings, name="compare"),
    path("<int:pk>/", views.listing_detail, name="detail"),
]