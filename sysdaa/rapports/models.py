from __future__ import annotations

from django.utils import timezone


def _rapport_html_upload_to(instance, filename: str) -> str:
    annee = getattr(instance, "annee", timezone.now().year)
    mois = getattr(instance, "mois", timezone.now().month)
    type_rapport = getattr(instance, "type_rapport", "rapport").lower()

    ym = f"{int(annee):04d}/{int(mois):02d}"
    return (
        f"rapports/{ym}/"
        f"{type_rapport}_{int(annee):04d}_{int(mois):02d}_{timezone.now():%Y%m%d_%H%M%S}.html"
    )


def _rapport_json_upload_to(instance, filename: str) -> str:
    annee = getattr(instance, "annee", timezone.now().year)
    mois = getattr(instance, "mois", timezone.now().month)
    type_rapport = getattr(instance, "type_rapport", "rapport").lower()

    ym = f"{int(annee):04d}/{int(mois):02d}"
    return (
        f"rapports/{ym}/"
        f"{type_rapport}_{int(annee):04d}_{int(mois):02d}_{timezone.now():%Y%m%d_%H%M%S}.json"
    )