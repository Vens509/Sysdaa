from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.shortcuts import render
from django.urls import include, path

from two_factor.admin import AdminSiteOTPRequired
from two_factor import urls as tf_urls

from core.views import CustomLoginView

admin.site.__class__ = AdminSiteOTPRequired

two_factor_patterns, two_factor_app_name = tf_urls.urlpatterns
two_factor_patterns = list(two_factor_patterns)

if two_factor_patterns:
    two_factor_patterns[0] = path(
        "account/login/",
        CustomLoginView.as_view(),
        name="login",
    )

urlpatterns = [
    path("admin/", admin.site.urls),

    # Login personnalisé principal
    path("login/", CustomLoginView.as_view(), name="custom_login"),

    # URLs two-factor avec login remplacé par la même vue personnalisée
    path(
        "",
        include((two_factor_patterns, two_factor_app_name), namespace=two_factor_app_name),
    ),

    # Logout
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # Apps
    path("", include("core.urls")),
    path("utilisateurs/", include("utilisateurs.urls")),
    path("articles/", include("articles.urls")),
    path("fournisseurs/", include("fournisseurs.urls")),
    path("requisitions/", include("requisitions.urls")),
    path("mouvements/", include("mouvements_stock.urls")),
    path("notifications/", include("notifications.urls")),
    path("rapports/", include("rapports.urls")),
    path("audit/", include("audit.urls")),
    path("configurations/", include("configurations.urls")),
]


def custom_403(request, exception=None):
    return render(request, "403.html", status=403)


handler403 = "sysdaa.urls.custom_403"