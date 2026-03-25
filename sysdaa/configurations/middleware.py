from __future__ import annotations

from .services import (
    assurer_annee_fiscale_active_auto,
    assurer_bascule_stock_mensuelle_auto,
)


class AutoAnneeFiscaleMiddleware:
    """
    À chaque ouverture du système :
    - on vérifie l'année fiscale
    - si elle a changé, on bascule automatiquement
    - si elle n'a pas changé, aucune écriture BD n'est faite

    Puis :
    - on vérifie la bascule mensuelle du stock
    - au premier accès d'un nouveau mois, le stock actuel devient
      le stock initial du mois
    - cette opération ne s'exécute qu'une seule fois par période
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            assurer_annee_fiscale_active_auto(configurateur=getattr(request, "user", None))
        except Exception:
            pass

        try:
            assurer_bascule_stock_mensuelle_auto(configurateur=getattr(request, "user", None))
        except Exception:
            pass

        return self.get_response(request)
