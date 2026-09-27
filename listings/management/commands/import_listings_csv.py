import csv
from decimal import Decimal,InvalidOperation
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from listings.models import Listing, ListingPriceSnapshot, ImportRun

class Command(BaseCommand):
    help = "Importar o actualiza propiedades desde un archivo csv."

    def add_arguments(self, parser):

        parser.add_argument(
            "file_path",
            type = str,
            help = "Ruta del archivo csv que desea importar."
        )

        parser.add_argument(
            "--dry-run",
            action = "store_true",
            help = "Revisa el CSV sin crear ni actualizar propiedades."
        )

        parser.add_argument(
            "--deactivate-missing",
            action = "store_true",
            help = (
                "Desactiva propiedades activas de las fuentes incluidas "
                "en el csv que no aparezcan en esta importacion."
            ),
        )



    def decimal_or_none(self,value):
        if not value:
            return None
        try:
            return Decimal(value)
        except InvalidOperation:
            return None

    def integer_or_none(self, value):
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def boolean_value(self, value):
        return str(value).strip().lower() in ['true', '1', 'yes', "si", "sí"]

    def handle(self, *args, **options):
        file_path = Path(options["file_path"])
        dry_run = options["dry_run"]
        deactivate_missing = options["deactivate_missing"]
        import_started_at = timezone.now()

        if not file_path.exists():
            raise CommandError(f"No se encontro el archivo: {file_path}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Modo simulacion: no se haran cambios en la base de datos."
                )
            )



        required_columns ={
            "source",
             "source_listing_id",
            "source_url",
            "property_type",
            "operation_type",
            "sector",
            "city",
            "price",
            "currency",
            "area_m2",
            "bedrooms",
            "bathrooms",
            "parking_spaces",
            "is_active",

        }

        created_count = 0
        updated_count = 0
        skipped_count = 0
        deactivated_count = 0
        processed_listing_keys = set()
        imported_sources = set()


        with file_path.open(encoding ="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)

            if not reader.fieldnames:
                raise CommandError("El archivo CSV no tiene encabezados de colummna.")

            missing_columns = required_columns - set(reader.fieldnames)

            if missing_columns:
                missing = " , ".join(sorted(missing_columns))
                raise CommandError(f"Faltan estas columnas: {missing}")

            for line_number, row in enumerate(reader, start=2):
                source = (row["source"] or "manual").strip().lower()
                source_listing_id = (row["source_listing_id"] or "").strip()
                source_url = (row["source_url"] or "").strip()

                if not source_listing_id or not source_url:
                    self.stdout.write(self.style.WARNING(
                        f"Línea {line_number}: Ignorada falta ID o URL"
                    ))
                    skipped_count += 1
                    continue

                listing_key = (source, source_listing_id)

                if listing_key in processed_listing_keys:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Linea {line_number}: Ignorada porque la propiedad "
                            f"{source_listing_id} esta repetida en el CSV."
                        )
                    )
                    skipped_count += 1
                    continue

                property_type = (row["property_type"] or Listing.PropertyType.APARTMENT).strip()
                operation_type = (row["operation_type"] or Listing.OperationType.SALE).strip()
                sector = (row["sector"] or "").strip()
                city = (row["city"] or "Santo Domingo").strip()
                price = self.decimal_or_none(row["price"])
                currency = (row["currency"] or Listing.Currency.USD).strip().upper()
                area_m2 = self.decimal_or_none(row["area_m2"])
                bedrooms = self.integer_or_none(row["bedrooms"])
                bathrooms = self.decimal_or_none(row["bathrooms"])
                parking_spaces = self.integer_or_none(row["parking_spaces"])

                errors = []

                if source not in Listing.Source.values:
                    errors.append("fuente no valida")

                if property_type not in Listing.PropertyType.values:
                    errors.append("tipo de propiedad no valida")

                if operation_type not in Listing.OperationType.values:
                    errors.append("tipo de operacion no valida")

                if currency not in Listing.Currency.values:
                    errors.append("moneda no valida")

                if not sector:
                    errors.append("sector no puede estar vacio")

                if price is None or price <= 0:
                    errors.append("precio invalido")

                if area_m2 is None or area_m2 <= 0:
                    errors.append("area invalida")

                if errors:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Linea {line_number}: ignorada - "
                            f"{', '.join(errors)}"
                        )
                    )
                    skipped_count += 1
                    continue

                processed_listing_keys.add(listing_key)
                imported_sources.add(source)

                defaults = {
                     "source_url": source_url,
                    "property_type":property_type,
                    "operation_type":operation_type,
                    "sector": sector,
                    "city": city,
                    "price": price,
                    "currency": currency,
                    "area_m2": area_m2,
                    "bedrooms": bedrooms,
                    "bathrooms": bathrooms,
                    "parking_spaces": parking_spaces,
                    "is_active": self.boolean_value(row["is_active"]),
                    "last_seen_at": timezone.now()
                }
                              
                '''listing, created = Listing.objects.update_or_create(
                    source = source,
                    source_listing_id = source_listing_id,
                    defaults = defaults
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1'''

                existing_listing = Listing.objects.filter(
                    source = source,
                    source_listing_id = source_listing_id,

                ).first()

                if existing_listing:
                    if not dry_run:
                        old_price = existing_listing.price
                        old_currency = existing_listing.currency

                        for field_name,value in defaults.items():
                            setattr(existing_listing, field_name, value)

                        existing_listing.save()

                        price_changed = (
                            old_price != existing_listing.price
                            or old_currency != existing_listing.currency
                        )

                        has_history = existing_listing.price_history.exists()

                        if (
                            existing_listing.price is not None
                            and (price_changed or not has_history)
                        ):
                            ListingPriceSnapshot.objects.create(
                                listing = existing_listing,
                                price = existing_listing.price,
                                currency = existing_listing.currency
                            )

                    updated_count +=1

                else:
                    if not dry_run:
                        listing = Listing.objects.create(
                            source = source,
                            source_listing_id = source_listing_id,
                            **defaults,
                        )

                        if listing.price is not None:
                            ListingPriceSnapshot.objects.create(
                                listing = listing,
                                price = listing.price,
                                currency = listing.currency,
                            )
                    created_count +=1

            if deactivate_missing and imported_sources:
                listings_to_deactivate = Listing.objects.filter(
                    is_active = True,
                    source__in = imported_sources,
                    last_seen_at__lt = import_started_at,
                )

                deactivated_count = listings_to_deactivate.count()

                if not dry_run:
                    listings_to_deactivate.update(is_active = False)

                action_text = (
                    "se desactivarian"
                    if dry_run
                    else "se desactivaron"
                )

                self.stdout.write(
                    self.style.WARNING(
                        f"{action_text} {deactivated_count} propiedades "
                        "que no aparecen en el CSV actual."
                    )
                )

            if not dry_run:
                ImportRun.objects.create(
                    sources=", ".join(sorted(imported_sources)),
                    file_name= file_path.name,
                    created_count = created_count,
                    updated_count = updated_count,
                    skipped_count = skipped_count,
                    deactivated_count = deactivated_count,
                    completed_at = timezone.now(),
                )


            summary_prefix = (
                "Simulación completada: "
                if dry_run 
                else "Importacion completada: "
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"{summary_prefix}"
                    f"{created_count} propiedades creadas,"
                    f"{updated_count} propiedades actualizadas,"
                    f"{skipped_count} propiedades ignoradas,"
                    f"{deactivated_count} propiedades desactivadas."
                )
            )