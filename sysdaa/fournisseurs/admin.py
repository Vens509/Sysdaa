from django.contrib import admin
from .models import AdresseFournisseur, ArticleFournisseur, Fournisseur


class AdresseInline(admin.TabularInline):
    model = AdresseFournisseur
    extra = 0


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ("id", "nom")
    search_fields = ("nom",)
    inlines = [AdresseInline]


@admin.register(ArticleFournisseur)
class ArticleFournisseurAdmin(admin.ModelAdmin):
    list_display = ("article", "fournisseur")
    search_fields = ("article__nom", "fournisseur__nom")