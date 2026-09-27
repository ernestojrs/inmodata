from django.contrib import admin
from .models import Listing, ListingPriceSnapshot, ImportRun

# Register your models here.

class ListingPriceSnapshotInline(admin.TabularInline):
    model = ListingPriceSnapshot
    extra = 0
    can_delete = False
    readonly_fields = (
        "price",
        "currency",
        "recorded_at",
    )

@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "city",
        "source_listing_id",
        "sector",
        "property_type",
        "operation_type",
        "price",
        "currency",
        "area_m2",
        "is_active",
        "last_seen_at",
    )

    list_filter= (
        "source",
        "property_type",
        "operation_type",
        "currency",
        "is_active",
        "sector",
        "city",
    )

    search_fields = (
        "source_listing_id",
        "sector",
        "city",
        "source_url",
    )

    ordering = ("-last_seen_at",)
    readonly_fields = (
        "first_seen_at",
        "created_at",
        "updated_at",
        "last_seen_at",
        "price_per_m2_display",
    )

    inlines = [ListingPriceSnapshotInline]

    fieldsets = (
        (
            "Identificación y fuente",
            {
                "fields":(
                    "source",
                    "source_listing_id",
                    "source_url",
                )

            },
        ),

        (
            "ubicación y tipo",
            {
                "fields":(
                    "property_type",
                    "operation_type",
                    "sector",
                    "city",
                )
            }
        ),

        (
            "precio y caracteristicas",
            {
                "fields":(
                    "price",
                    "currency",
                    "area_m2",
                    "price_per_m2_display",
                    "bedrooms",
                    "bathrooms",
                    "parking_spaces",
                )
            }
        ),

        (
            "estado y fechas",
            {
                "fields":(
                    "is_active",
                    "first_seen_at",
                    "last_seen_at",
                    "created_at",
                    "updated_at",
                )
            }
        ),
    )


    @admin.display(description="Precio por m²")
    def price_per_m2_display(self, obj):
        if obj.price_per_m2 is None:
            return "-"

        return f"{obj.currency} {obj.price_per_m2:,.2f}"

@admin.register(ImportRun)
class ImportRunAdmin(admin.ModelAdmin):
     list_display = (
        "completed_at",
        "sources",
        "file_name",
        "created_count",
        "updated_count",
        "skipped_count",
        "deactivated_count",
    )

     list_filter = ("completed_at",)

     search_fields = (
         "sources",
         "file_name",
     )

     readonly_fields = (
        "sources",
        "file_name",
        "created_count",
        "updated_count",
        "skipped_count",
        "deactivated_count",
        "completed_at",
     )

