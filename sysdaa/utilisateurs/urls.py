from django.urls import path
from . import views

app_name = "utilisateurs"

urlpatterns = [
    path("", views.liste_utilisateurs, name="liste"),
    path("creer/", views.creer_utilisateur_view, name="creer"),

    path("<int:pk>/modifier/", views.modifier_utilisateur_view, name="modifier"),
    path("<int:pk>/toggle-statut/", views.toggle_statut_utilisateur_view, name="toggle_statut"),
    path("<int:pk>/reset-password/", views.reset_password_utilisateur_view, name="reset_password"),
]