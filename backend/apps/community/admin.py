from django.contrib import admin
from django.db.models import Count

from .models import ProductReport, ReportFlag, ReportPhoto


class ReportPhotoInline(admin.TabularInline):
    model = ReportPhoto
    extra = 0


@admin.register(ProductReport)
class ProductReportAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "verdict", "flag_count", "is_hidden", "created_at")
    list_filter = ("verdict", "is_hidden")
    search_fields = ("product__barcode", "product__name", "user__username")
    actions = ["hide_reports", "unhide_reports"]
    inlines = [ReportPhotoInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_flag_count=Count("flags"))

    @admin.display(ordering="_flag_count", description="Flags")
    def flag_count(self, obj):
        return obj._flag_count

    @admin.action(description="Hide selected reports (exclude from integrity score)")
    def hide_reports(self, request, queryset):
        queryset.update(is_hidden=True)

    @admin.action(description="Unhide selected reports")
    def unhide_reports(self, request, queryset):
        queryset.update(is_hidden=False)


admin.site.register(ReportFlag)
