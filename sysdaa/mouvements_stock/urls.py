from django.urls import path
from . import views

app_name = "mouvements_stock"

urlpatterns = [
    path("entree/", views.entree_stock, name="entree_stock"),
    path("sortie/", views.sortie_stock, name="sortie_stock"),
    path("mouvements/", views.liste_mouvements, name="liste_mouvements"),
    path("etat/", views.etat_stock, name="etat_stock"),
]
