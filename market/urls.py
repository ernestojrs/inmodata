from django.urls import path

from . import views

app_name = "market"

urlpatterns = [
    path("", views.market_overview, name="overview"),
    path("valorar/", views.valuation, name="valuation"),
    path("oportunidades/", views.opportunities, name="opportunities"),
    path("financiamiento/", views.mortgage_calculator, name="mortgage"),
    path("bajas-de-precio/", views.price_drops, name="price_drops"),
    path("sector/<str:sector>/", views.sector_detail, name="sector_detail"),
    path(
        "alquileres/",
        views.rental_market_overview,
        name="rental_overview",
    ),
    path(
        "valorar-alquiler/",
        views.rental_valuation,
        name="rental_valuation",
    ),

    path(
    "rentabilidad-alquiler/",
    views.rental_yield,
    name="rental_yield",
    ),

    path(
    "alquileres/sector/<str:sector>/",
    views.rental_sector_detail,
    name="rental_sector_detail",
    ),
]