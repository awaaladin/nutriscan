from django.contrib import admin, messages

from . import corrections
from .models import DataCorrection, KnowledgeEntry, ProductEvidence


@admin.register(ProductEvidence)
class ProductEvidenceAdmin(admin.ModelAdmin):
    list_display = ("product", "source_type", "source_label", "status", "match_score", "created_at")
    list_filter = ("source_type", "status")
    search_fields = ("product__name", "product__barcode", "source_label")
    readonly_fields = ("product", "source_type", "source_ref", "source_label", "facts", "match_score", "status", "note", "created_at")

    def has_add_permission(self, request):
        return False  # evidence is recorded by the research and correction steps, not typed in


@admin.register(DataCorrection)
class DataCorrectionAdmin(admin.ModelAdmin):
    list_display = ("product", "field", "current_value", "suggested_value", "user", "status", "created_at")
    list_filter = ("status", "field")
    search_fields = ("product__name", "product__barcode")
    actions = ["accept_corrections", "reject_corrections"]

    @admin.action(description="Accept: apply the suggested value to the product")
    def accept_corrections(self, request, queryset):
        done = 0
        for correction in queryset.filter(status=DataCorrection.Status.OPEN):
            corrections.accept(correction)
            done += 1
        self.message_user(request, f"Applied {done} correction(s).", messages.SUCCESS)

    @admin.action(description="Reject the selected corrections")
    def reject_corrections(self, request, queryset):
        queryset.filter(status=DataCorrection.Status.OPEN).update(status=DataCorrection.Status.REJECTED)


@admin.register(KnowledgeEntry)
class KnowledgeEntryAdmin(admin.ModelAdmin):
    """The reviewed knowledge base the assistant answers from. Entries built from chats
    arrive unapproved: edit them (remove anything personal), then approve."""

    list_display = ("question", "topic", "source", "approved", "created_at")
    list_filter = ("approved", "source", "topic")
    search_fields = ("question", "answer")
    actions = ["approve_entries", "unapprove_entries"]

    @admin.action(description="Approve: the assistant may use these")
    def approve_entries(self, request, queryset):
        queryset.update(approved=True)

    @admin.action(description="Withdraw approval")
    def unapprove_entries(self, request, queryset):
        queryset.update(approved=False)
