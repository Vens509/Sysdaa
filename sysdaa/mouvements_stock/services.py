from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from configurations.services import (
    assurer_annee_fiscale_active_pour_date,
    assurer_bascule_stock_mensuelle_pour_date,
)

from .models import MouvementStock


@dataclass(slots=True)
class MouvementResult:
    mouvement_id: int
    nouveau_stock: int
    quantite_unites: int


def _normaliser_conditionnement(
    *,
    article,
    conditionnement_mouvement: str | None,
    quantite_par_conditionnement_mouvement: int | None,
) -> tuple[str, int]:
    conditionnement = (conditionnement_mouvement or "").strip() or "Unité"
    qpc = int(quantite_par_conditionnement_mouvement or 0)

    if conditionnement.casefold() in {"unité", "unite"}:
        return "Unité", 1

    if conditionnement == getattr(article, "unite", ""):
        return conditionnement, int(article.quantite_par_conditionnement or 1)

    if qpc <= 0:
        raise ValueError(
            "Le nombre d’unités par conditionnement de l’opération doit être supérieur à 0."
        )

    return conditionnement, qpc


@transaction.atomic
def enregistrer_entree_stock(
    *,
    article,
    quantite: int,
    conditionnement_mouvement: str | None = None,
    quantite_par_conditionnement_mouvement: int | None = None,
    date_mouvement=None,
    acteur=None,
) -> MouvementResult:
    quantite = int(quantite or 0)
    if quantite <= 0:
        raise ValueError("La quantité doit être > 0.")

    conditionnement, qpc_mvt = _normaliser_conditionnement(
        article=article,
        conditionnement_mouvement=conditionnement_mouvement,
        quantite_par_conditionnement_mouvement=quantite_par_conditionnement_mouvement,
    )
    quantite_unites = quantite * qpc_mvt

    mouvement_dt = date_mouvement or timezone.now()

    assurer_annee_fiscale_active_pour_date(
        date_reference=mouvement_dt,
        configurateur=acteur,
    )
    assurer_bascule_stock_mensuelle_pour_date(
        date_reference=mouvement_dt,
        configurateur=acteur,
    )

    article_locked = type(article).objects.select_for_update().get(pk=article.pk)

    stock_actuel = getattr(article_locked, "stock_actuel", None)
    if stock_actuel is None:
        raise ValueError("Le champ stock_actuel est introuvable sur l'article.")

    initialiser_stock = article_locked.peut_initialiser_stock_depuis_entree()

    if initialiser_stock:
        article_locked.autoriser_mise_a_jour_systeme_stock_initial()
        article_locked.stock_initial = quantite_unites
        article_locked.stock_actuel = quantite_unites
        update_fields = ["stock_initial", "stock_actuel"]
    else:
        article_locked.stock_actuel = int(stock_actuel) + quantite_unites
        update_fields = ["stock_actuel"]

    article_locked.full_clean()
    article_locked.save(update_fields=update_fields)

    mv = MouvementStock(
        article=article_locked,
        requisition=None,
        motif_sortie="",
        quantite=quantite,
        conditionnement_mouvement=conditionnement,
        quantite_par_conditionnement_mouvement=qpc_mvt,
        quantite_unites=quantite_unites,
        type_mouvement=MouvementStock.TypeMouvement.ENTREE,
        date_mouvement=mouvement_dt,
    )
    mv.full_clean()
    mv.save()

    return MouvementResult(
        mouvement_id=mv.id,
        nouveau_stock=article_locked.stock_actuel,
        quantite_unites=quantite_unites,
    )


@transaction.atomic
def enregistrer_sortie_stock(
    *,
    article,
    quantite: int,
    motif_sortie: str = "",
    requisition=None,
    conditionnement_mouvement: str | None = None,
    quantite_par_conditionnement_mouvement: int | None = None,
    date_mouvement=None,
    acteur=None,
) -> MouvementResult:
    quantite = int(quantite or 0)
    if quantite <= 0:
        raise ValueError("La quantité doit être > 0.")

    conditionnement, qpc_mvt = _normaliser_conditionnement(
        article=article,
        conditionnement_mouvement=conditionnement_mouvement,
        quantite_par_conditionnement_mouvement=quantite_par_conditionnement_mouvement,
    )
    quantite_unites = quantite * qpc_mvt

    mouvement_dt = date_mouvement or timezone.now()
    motif_sortie = (motif_sortie or "").strip()

    assurer_annee_fiscale_active_pour_date(
        date_reference=mouvement_dt,
        configurateur=acteur,
    )
    assurer_bascule_stock_mensuelle_pour_date(
        date_reference=mouvement_dt,
        configurateur=acteur,
    )

    article_locked = type(article).objects.select_for_update().get(pk=article.pk)

    stock_actuel = getattr(article_locked, "stock_actuel", None)
    if stock_actuel is None:
        raise ValueError("Le champ stock_actuel est introuvable sur l'article.")

    stock_actuel = int(stock_actuel)
    if quantite_unites > stock_actuel:
        raise ValueError(
            "Stock insuffisant pour effectuer cette sortie. "
            f"Disponibilité actuelle : {article_locked.stock_actuel_affichage}."
        )

    article_locked.stock_actuel = stock_actuel - quantite_unites
    article_locked.full_clean()
    article_locked.save(update_fields=["stock_actuel"])

    mv = MouvementStock(
        article=article_locked,
        requisition=requisition,
        motif_sortie=motif_sortie if requisition is None else "",
        quantite=quantite,
        conditionnement_mouvement=conditionnement,
        quantite_par_conditionnement_mouvement=qpc_mvt,
        quantite_unites=quantite_unites,
        type_mouvement=MouvementStock.TypeMouvement.SORTIE,
        date_mouvement=mouvement_dt,
    )
    mv.full_clean()
    mv.save()

    return MouvementResult(
        mouvement_id=mv.id,
        nouveau_stock=article_locked.stock_actuel,
        quantite_unites=quantite_unites,
    )