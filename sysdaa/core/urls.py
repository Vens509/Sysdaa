from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard-secretaire/", views.dashboard_secretaire, name="dashboard_secretaire"),
    path("a-confirmer/", views.a_confirmer, name="a_confirmer"),
    path("dashboard-admin/", views.dashboard_admin, name="dashboard_admin"),
    path("compte/mot-de-passe/", views.password_change, name="password_change"),
    path("compte/mot-de-passe/ok/", views.password_change_done, name="password_change_done"),
]