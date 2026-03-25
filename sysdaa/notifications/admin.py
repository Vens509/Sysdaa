from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "destinataire", "lu", "date_creation", "titre", "requisition")
    list_filter = ("lu", "date_creation")
    search_fields = ("titre", "message", "destinataire__username")
    autocomplete_fields = ("destinataire", "requisition")
    ordering = ("-date_creation", "-id")
