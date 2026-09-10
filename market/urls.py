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
]