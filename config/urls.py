"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', core_views.home, name='home'),
    path("mercado/", include("market.urls")),
    path("propiedades/", include("listings.urls")),
    path("metodologia/", core_views.methodology, name="methodology"),
    path("privacidad/", core_views.privacy, name="privacy"),
    path("terminos/", core_views.terms, name="terms"),
    path("sitemap.xml", core_views.sitemap, name="sitemap"),
    path("robots.txt", core_views.robots_txt, name="robots_txt"),
    path("datos/", core_views.data_status, name="data_status"),
]
