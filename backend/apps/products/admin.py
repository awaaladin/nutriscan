from django.contrib import admin
from django.utils.html import format_html

from apps.community.nafdac import GREENBOOK_URL

from .models import CachedExplanation, Product, ProductSubmission


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "barcode", "product_type", "nafdac_number", "nafdac_verified", "manufacturer_verified")
    list_filter = ("product_type", "nafdac_verified", "manufacturer_verified", "source")
    search_fields = ("name", "barcode", "nafdac_number")
    readonly_fields = ("greenbook_link",)
    actions = ["mark_nafdac_verified", "mark_manufacturer_verified", "clear_verification"]

    @admin.display(description="Check on NAFDAC Greenbook")
    def greenbook_link(self, obj):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Open the Greenbook and search for {}</a>',
            GREENBOOK_URL,
            obj.nafdac_number or obj.name,
        )

    @admin.action(description="Mark NAFDAC number verified (after checking the Greenbook)")
    def mark_nafdac_verified(self, request, queryset):
        # A number must exist to be verified.
        queryset.exclude(nafdac_number="").update(nafdac_verified=True)

    @admin.action(description="Mark manufacturer verified")
    def mark_manufacturer_verified(self, request, queryset):
        queryset.update(manufacturer_verified=True)

    @admin.action(description="Clear NAFDAC / manufacturer verification")
    def clear_verification(self, request, queryset):
        queryset.update(nafdac_verified=False, manufacturer_verified=False)


admin.site.register(ProductSubmission)
admin.site.register(CachedExplanation)
