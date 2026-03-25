from django.contrib import admin

from .models import ClotureStockMensuelle, ConfigurationSysteme


@admin.register(ConfigurationSysteme)
class ConfigurationSystemeAdmin(admin.ModelAdmin):
    list_display = ("id", "annee_debut", "annee_fin", "est_active", "configurateur")
    list_filter = ("est_active",)
    search_fields = ("annee_debut", "annee_fin", "configurateur__email")
    ordering = ("-annee_debut", "-id")


@admin.register(ClotureStockMensuelle)
class ClotureStockMensuelleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "annee",
        "mois",
        "nombre_articles_total",
        "nombre_articles_mis_a_jour",
        "date_execution",
        "configurateur",
    )
    list_filter = ("annee", "mois")
    search_fields = ("annee", "mois", "configurateur__email")
    ordering = ("-annee", "-mois", "-id")
