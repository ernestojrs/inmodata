from django.urls import path
from . import views
app_name = "listings"

urlpatterns = [
    path("", views.listings_list, name="list"),
    path("comparar/", views.compare_listings, name="compare"),
    path(
    "<int:pk>/favorito/",
    views.toggle_favorite,
    name="toggle_favorite",
    ),
        path(
        "favoritos/",
        views.favorites_list,
        name="favorites",
    ),
    path(
        "busquedas/guardar/",
        views.save_search,
        name="save_search",
    ),
    path("<int:pk>/", views.listing_detail, name="detail"),
    path("importar/", views.import_listings_upload, name="import_upload"),
    path("exportar/", views.export_listings_csv, name="export_csv"),
    path(
    "respaldo/",
    views.export_listings_backup,
    name="export_backup",
    ),
   path(
        "busquedas/",
        views.saved_searches,
        name="saved_searches",
    ),
    path(
        "busquedas/<int:pk>/eliminar/",
        views.delete_saved_search,
        name="delete_saved_search",
    ),
    path(
        "alquileres/",
        views.rentals_list,
        name="rentals",
    ),
    
]