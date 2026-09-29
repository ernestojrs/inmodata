from django.test import TestCase, override_settings
from django.urls import reverse
from decimal import Decimal
from listings.models import Listing

# Create your tests here.



class HomePageTests(TestCase):
    def test_home_page_loads_main_tools(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Explorar propiedades")
        self.assertContains(response, "¿El precio es justo?")
        self.assertContains(response, "Encuentra mejores valores")
        self.assertContains(response, "Calcula tu cuota")

    def test_methodology_page_loads(self):
        response = self.client.get(
            reverse("methodology"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cómo calcula InmoData")
        self.assertContains(response, "Precio por metro cuadrado")

    def test_privacy_page_loads(self):
        response = self.client.get(reverse("privacy"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Política de privacidad")
        self.assertContains(response, "Publicidad y analítica")

    def test_terms_page_loads(self):
        response = self.client.get(reverse("terms"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Términos de uso")
        self.assertContains(response, "No es una tasación")

    def test_sitemap_includes_active_listing(self):
        listing = Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="SITEMAP-001",
            source_url="https://example.com/sitemap-001",
            sector="Naco",
            city="Santo Domingo",
            price=Decimal("200000"),
            area_m2=Decimal("100"),
        )

        response = self.client.get(reverse("sitemap"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f"/propiedades/{listing.pk}/",
        )


    def test_robots_txt_includes_sitemap(self):
        response = self.client.get(reverse("robots_txt"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User-agent: *")
        self.assertContains(response, "Sitemap:")

    @override_settings(DEBUG=False)
    def test_custom_404_page_loads(self):
        response = self.client.get("/pagina-que-no-existe/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Esta página no existe.", status_code=404)
        self.assertContains(
            response,
            "Explorar propiedades disponibles",
            status_code=404,
        )

    def test_data_status_page_loads(self):
        Listing.objects.create(
            source=Listing.Source.MANUAL,
            source_listing_id="STATUS-001",
            source_url="https://example.com/status-001",
            sector="Naco",
            city="Santo Domingo",
            price=Decimal("200000"),
            area_m2=Decimal("100"),
        )

        response = self.client.get(reverse("data_status"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Estado de los datos")
        self.assertContains(response, "Naco")
        self.assertContains(response, "1")
  

    