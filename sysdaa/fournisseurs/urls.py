from django.urls import path
from . import views

app_name = "fournisseurs"

urlpatterns = [
    path("", views.liste_fournisseurs, name="liste"),
    path("creer/", views.creer_fournisseur, name="creer"),
    path("<int:pk>/", views.detail_fournisseur, name="detail"),
    path("<int:pk>/modifier/", views.modifier_fournisseur, name="modifier"),
    path("<int:pk>/supprimer/", views.supprimer_fournisseur, name="supprimer"),

    path("<int:fournisseur_pk>/adresses/ajouter/", views.ajouter_adresse, name="adresse_ajouter"),
    path("<int:fournisseur_pk>/adresses/<int:pk>/supprimer/", views.supprimer_adresse, name="adresse_supprimer"),

    path("<int:fournisseur_pk>/articles/lier/", views.lier_article, name="lier_article"),
    path("<int:fournisseur_pk>/articles/<int:article_pk>/supprimer/", views.supprimer_liaison, name="supprimer_liaison"),
]