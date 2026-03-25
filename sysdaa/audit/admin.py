from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "date_action",
        "niveau",
        "app",
        "action",
        "succes",
        "acteur",
        "identifiant_saisi",
        "cible_type",
        "cible_id",
    )
    list_filter = ("niveau", "succes", "app", "action", "date_action")
    search_fields = (
        "message",
        "identifiant_saisi",
        "acteur__email",
        "acteur__nom",
        "acteur__prenom",
        "cible_type",
        "cible_id",
        "cible_label",
    )
    readonly_fields = (
        "date_action",
        "niveau",
        "app",
        "action",
        "acteur",
        "identifiant_saisi",
        "ip",
        "user_agent",
        "cible_type",
        "cible_id",
        "cible_label",
        "message",
        "details",
        "succes",
    )
    ordering = ("-date_action", "-id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False