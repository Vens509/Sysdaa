from __future__ import annotations

from django.urls import path

from . import views

app_name = "rapports"

urlpatterns = [
    path("", views.generer, name="generer"),
    path("export/excel/", views.export_excel, name="export_excel"),
    path("export/pdf/", views.export_pdf, name="export_pdf"),
]