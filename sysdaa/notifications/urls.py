from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("ouvrir/<int:id>/", views.ouvrir, name="ouvrir"),
    path("marquer-lu/<int:id>/", views.marquer_lu, name="marquer_lu"),
    path("supprimer-selection/", views.supprimer_selection, name="supprimer_selection"),
    path("supprimer-lues/", views.supprimer_lues, name="supprimer_lues"),
    path("live/", views.notifications_live, name="notifications_live"),
]