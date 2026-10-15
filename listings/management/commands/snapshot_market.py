from collections import defaultdict
from datetime import date
from statistics import median
from django.core.management.base import BaseCommand
from django.utils import timezone
from listings.models import Listing, SectorMarketSnapshot

class Command(BaseCommand):
    help = (
         "Guarda una fotografía diaria del mercado por sector "
            "usando propiedades activas."
    )

    def add_arguments(self,parser):
        parser.add_argument(
            "--date",
            type = date.fromisoformat,
            dest = "snapshot_date",
            help = "Fecha de la fotografía: AAAA-MM-DD.",
        )

    def handle(self,*args,**options):
        snapshot_date = (
            options["snapshot_date"]
            or timezone.localdate()
        )

        listings = (
            Listing.objects.filter(is_active=True).exclude(sector="")
        )

        prices_by_sector = defaultdict(list)

        for listing in listings:
            price_per_m2 = listing.price_per_m2

            if price_per_m2 is not None:
                prices_by_sector[listing.sector.strip()].append(price_per_m2)

        created_count = 0
        updated_count = 0

        for sector,prices_per_m2 in prices_by_sector.items():
            _, created = (
                SectorMarketSnapshot.objects.update_or_create(
                    city = "Santo Domingo",
                    sector = sector,
                    snapshot_date = snapshot_date,
                    defaults = {
                        "listings_count": len(prices_per_m2),
                        "median_price_per_m2": median(prices_per_m2),
                    },
                )
            )

            if created:
                created_count += 1
            else:
                updated_count += 1


        self.stdout.write(
        self.style.SUCCESS(
            "Fotografía guardada: "
            f"{created_count} sectores creados, "
            f"{updated_count} sectores actualizados."
        )
    )
           