from django.contrib import admin

from .models import Article, Categorie


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ("id", "libelle")
    search_fields = ("libelle",)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nom",
        "unite",
        "quantite_par_conditionnement",
        "categorie",
        "stock_initial",
        "stock_actuel",
        "stock_minimal",
        "utilisateur_enregistreur",
    )
    list_filter = ("categorie", "unite")
    search_fields = (
        "nom",
        "unite",
        "unite_base",
        "categorie__libelle",
        "utilisateur_enregistreur__email",
    )
    autocomplete_fields = ("categorie", "utilisateur_enregistreur")
    readonly_fields = ("date_creation", "date_modification")