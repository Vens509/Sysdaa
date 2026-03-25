from django.contrib import admin

from .models import Requisition, LigneRequisition


class LigneRequisitionInline(admin.TabularInline):
    model = LigneRequisition
    extra = 1
    autocomplete_fields = ["article"]
    fields = (
        "article",
        "unite_demandee",
        "quantite_demandee",
        "quantite_demandee_unites",
        "unite_livree",
        "quantite_livree",
        "quantite_livree_unites",
        "motif_article",
    )
    readonly_fields = ("quantite_demandee_unites", "quantite_livree_unites")


@admin.register(Requisition)
class RequisitionAdmin(admin.ModelAdmin):
    search_fields = ["id", "soumetteur__direction_affectee", "etat_requisition"]

    list_display = (
        "id",
        "direction_demandeuse_affiche",
        "etat_requisition",
        "date_preparation",
        "soumetteur",
    )

    list_filter = (
        "etat_requisition",
        "soumetteur__direction_affectee",
        "transferee_vers_directeur_daa",
    )

    def direction_demandeuse_affiche(self, obj):
        return obj.direction_demandeuse

    direction_demandeuse_affiche.short_description = "Direction demandeuse"

    fieldsets = (
        (
            "Informations Générales",
            {
                "fields": (
                    "direction_demandeuse_affiche",
                    "date_preparation",
                    "etat_requisition",
                    "soumetteur",
                )
            },
        ),
        (
            "Validation & Approbation",
            {
                "fields": (
                    "directeur_direction",
                    "transferee_vers_directeur_daa",
                    "date_transfert_directeur_daa",
                    "directeur_daa",
                    "sceau_directeur_daa",
                    "date_sceau_directeur_daa",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Modifications & Remarques",
            {
                "fields": (
                    "motif_global",
                    "remarque",
                    "demande_modification_motif",
                    "demande_modification_par",
                    "date_demande_modification",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Suivi Temporel",
            {
                "fields": ("date_approbation", "date_livraison", "date_reception", "traitee_par", "recue_par"),
            },
        ),
    )

    readonly_fields = (
        "direction_demandeuse_affiche",
        "sceau_directeur_daa",
        "date_sceau_directeur_daa",
    )
    inlines = [LigneRequisitionInline]


@admin.register(LigneRequisition)
class LigneRequisitionAdmin(admin.ModelAdmin):
    list_display = (
        "requisition",
        "article",
        "unite_demandee",
        "quantite_demandee",
        "quantite_demandee_unites",
        "unite_livree",
        "quantite_livree",
        "quantite_livree_unites",
    )
    search_fields = ["requisition__id", "article__nom"]
    autocomplete_fields = ["requisition", "article"]
    readonly_fields = ("quantite_demandee_unites", "quantite_livree_unites")