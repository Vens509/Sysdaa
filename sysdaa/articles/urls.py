from django.urls import path
from . import views

app_name = "articles"

urlpatterns = [
    path("", views.liste_articles, name="liste"),

    path("creer/", views.creer_article, name="creer"),
    path("ajouter/", views.creer_article, name="ajouter"),

    path("<int:pk>/", views.detail_article, name="detail"),
    path("<int:pk>/modifier/", views.modifier_article, name="modifier"),
    path("<int:pk>/supprimer/", views.supprimer_article, name="supprimer"),

    path("categories/", views.liste_categories, name="categories"),
    path("categories/creer/", views.creer_categorie, name="categorie_creer"),
    path("categories/ajouter/", views.creer_categorie, name="creer_categorie"),
    path("categories/<int:pk>/modifier/", views.modifier_categorie, name="categorie_modifier"),
    path("categories/<int:pk>/supprimer/", views.supprimer_categorie, name="categorie_supprimer"),
]