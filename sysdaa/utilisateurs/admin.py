from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Utilisateur, Role, Permission, RolePermission, Direction
from .forms import UtilisateurCreationForm, UtilisateurUpdateForm


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    search_fields = ("nom_role",)
    list_display = ("id", "nom_role")


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    search_fields = ("nom_permission",)
    list_display = ("id", "nom_permission")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("id", "role", "permission")
    list_filter = ("role", "permission")
    search_fields = ("role__nom_role", "permission__nom_permission")


@admin.register(Direction)
class DirectionAdmin(admin.ModelAdmin):
    search_fields = ("nom",)
    list_display = ("id", "nom")
    ordering = ("nom",)


@admin.register(Utilisateur)
class UtilisateurAdmin(DjangoUserAdmin):
    form = UtilisateurUpdateForm
    add_form = UtilisateurCreationForm

    ordering = ("email",)
    list_display = (
        "email",
        "nom",
        "prenom",
        "direction_affectee",
        "directeur_superviseur",
        "role",
        "statut",
        "is_active",
        "is_staff",
        "is_superuser",
    )
    list_filter = ("role", "statut", "is_active", "is_staff", "is_superuser")
    search_fields = (
        "email",
        "nom",
        "prenom",
        "direction_affectee__nom",
        "directeur_superviseur__nom",
        "directeur_superviseur__prenom",
        "directeur_superviseur__email",
        "role__nom_role",
    )

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Identité",
            {"fields": ("nom", "prenom", "direction_affectee", "directeur_superviseur", "role")},
        ),
        ("Statut métier", {"fields": ("statut",)}),
        (
            "Indicateurs métier",
            {"fields": ("is_directeur_direction", "is_assistant_directeur")},
        ),
        ("Statut Django", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Permissions Django", {"fields": ("groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_creation")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "nom",
                    "prenom",
                    "direction_affectee",
                    "directeur_superviseur",
                    "role",
                    "statut",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )

    readonly_fields = ("is_directeur_direction", "is_assistant_directeur", "date_creation", "last_login")