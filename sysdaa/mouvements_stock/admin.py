from django.contrib import admin

from .models import MouvementStock


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "type_mouvement",
        "article",
        "quantite",
        "requisition",
        "motif_sortie_resume",
        "date_mouvement",
    )
    list_filter = ("type_mouvement", "date_mouvement")
    search_fields = (
        "article__nom",
        "motif_sortie",
        "requisition__motif_global",
        "requisition__soumetteur__email",
    )
    autocomplete_fields = ("article", "requisition")
    ordering = ("-date_mouvement", "-id")

    @admin.display(description="Motif sortie")
    def motif_sortie_resume(self, obj):
        if not obj.motif_sortie:
            return "—"
        return obj.motif_sortie[:60]