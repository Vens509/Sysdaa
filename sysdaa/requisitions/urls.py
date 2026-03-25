from django.urls import path

from . import views

app_name = "requisitions"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("creer/", views.creer, name="creer"),
    path("mes/", views.mes_requisitions, name="mes"),
    path("traitees/", views.liste_traitees, name="liste_traitees"),

    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/pdf/", views.detail_pdf, name="detail_pdf"),
    path("<int:pk>/modifier/", views.modifier, name="modifier"),

    path("<int:pk>/valider-direction/", views.valider_direction, name="valider_direction"),
    path("<int:pk>/rejeter-direction/", views.rejeter_direction, name="rejeter_direction"),

    path("<int:pk>/demander-modification/", views.demander_modification_view, name="demander_modification"),

    path("<int:pk>/traiter/", views.traiter, name="traiter"),
    path("<int:pk>/accuser-reception/", views.accuser_reception_view, name="accuser_reception"),

    path("<int:pk>/transferer-daa/", views.transferer_daa, name="transferer_daa"),
    path("<int:pk>/valider-daa/", views.valider_daa, name="valider_daa"),
    path("<int:pk>/rejeter-daa/", views.rejeter_daa, name="rejeter_daa"),

    path("<int:pk>/rejeter-gestionnaire/", views.rejeter_gestionnaire_view, name="rejeter_gestionnaire"),
]