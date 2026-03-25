from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from articles.models import _normaliser_libelle_unite
from core.permissions import (
    ROLE_DIRECTEUR_DAA,
    ROLE_DIRECTEUR_DIRECTION,
    ROLE_GESTIONNAIRE,
)
from notifications.services import envoyer_notification_et_email

from .models import Requisition

User = get_user_model()


def _utilisateurs_actifs_par_role(nom_role: str):
    return User.objects.filter(role__nom_role=nom_role, statut="Actif")


def trouver_directeur_de_direction(*, direction: str) -> Optional[Any]:
    direction = (direction or "").strip()
    if not direction:
        return None

    return (
        User.objects.filter(
            role__nom_role=ROLE_DIRECTEUR_DIRECTION,
            statut="Actif",
            is_directeur_direction=True,
            direction_affectee__nom__iexact=direction,
        )
        .select_related("direction_affectee", "role")
        .order_by("id")
        .first()
    )


def _notify_one(
    *,
    destinataire,
    titre: str,
    message: str,
    requisition: Requisition,
    lien: str | None,
):
    envoyer_notification_et_email(
        destinataire=destinataire,
        titre=titre,
        message=message,
        requisition=requisition,
        lien=lien,
    )


def _notify_many(
    *,
    destinataires: Iterable[Any],
    titre: str,
    message: str,
    requisition: Requisition,
    lien: str | None,
):
    for u in destinataires:
        _notify_one(
            destinataire=u,
            titre=titre,
            message=message,
            requisition=requisition,
            lien=lien,
        )


def _lock_requisition(pk: int) -> Requisition:
    return Requisition.objects.select_for_update().get(pk=pk)


def _ensure_etat(req: Requisition, *etats_autorises: str) -> None:
    if req.etat_requisition not in etats_autorises:
        raise ValueError(
            f"Action refusée : état actuel = '{req.etat_requisition}', "
            f"attendu = {', '.join(etats_autorises)}."
        )


def _reparer_ligne_si_possible(ligne) -> None:
    """
    Répare les anciennes lignes créées avant l'introduction correcte
    du couple (unite_demandee, quantite_demandee_unites).
    """
    if ligne.article_id is None:
        raise ValueError("Réquisition invalide : ligne sans article.")

    article = ligne.article
    qd = int(ligne.quantite_demandee or 0)
    if qd <= 0:
        raise ValueError("Réquisition invalide : quantité demandée manquante ou invalide.")

    champs_a_maj: list[str] = []

    unite_demandee = _normaliser_libelle_unite(ligne.unite_demandee or "")
    if article.est_stocke_par_unite:
        unite_calculee = "Unité"
        qd_unites_calculee = qd
    else:
        unite_principale = _normaliser_libelle_unite(article.unite)
        unite_calculee = unite_demandee or "Unité"

        if unite_calculee not in {"Unité", unite_principale}:
            raise ValueError(
                f"Réquisition invalide : unité demandée invalide pour l'article '{article.nom}'."
            )

        try:
            qd_unites_calculee = article.convertir_vers_unites_base(qd, unite_calculee)
        except ValidationError as exc:
            raise ValueError(f"{article.nom} : {exc.messages[0]}")

    if _normaliser_libelle_unite(ligne.unite_demandee or "") != unite_calculee:
        ligne.unite_demandee = unite_calculee
        champs_a_maj.append("unite_demandee")

    if int(ligne.quantite_demandee_unites or 0) != int(qd_unites_calculee or 0):
        ligne.quantite_demandee_unites = int(qd_unites_calculee or 0)
        champs_a_maj.append("quantite_demandee_unites")

    unite_livree = _normaliser_libelle_unite(ligne.unite_livree or "")
    ql = int(ligne.quantite_livree or 0)

    if ql <= 0:
        if (ligne.unite_livree or "") != "":
            ligne.unite_livree = ""
            champs_a_maj.append("unite_livree")
        if int(ligne.quantite_livree_unites or 0) != 0:
            ligne.quantite_livree_unites = 0
            champs_a_maj.append("quantite_livree_unites")
    else:
        if article.est_stocke_par_unite:
            unite_livree_calculee = "Unité"
            ql_unites_calculee = ql
        else:
            unite_principale = _normaliser_libelle_unite(article.unite)
            unite_livree_calculee = unite_livree or unite_calculee or "Unité"

            if unite_livree_calculee not in {"Unité", unite_principale}:
                raise ValueError(
                    f"Réquisition invalide : unité livrée invalide pour l'article '{article.nom}'."
                )

            try:
                ql_unites_calculee = article.convertir_vers_unites_base(
                    ql,
                    unite_livree_calculee,
                )
            except ValidationError as exc:
                raise ValueError(f"{article.nom} : {exc.messages[0]}")

        if ql_unites_calculee > qd_unites_calculee:
            raise ValueError(
                f"Réquisition invalide : la quantité livrée dépasse la quantité demandée pour '{article.nom}'."
            )

        if _normaliser_libelle_unite(ligne.unite_livree or "") != unite_livree_calculee:
            ligne.unite_livree = unite_livree_calculee
            champs_a_maj.append("unite_livree")

        if int(ligne.quantite_livree_unites or 0) != int(ql_unites_calculee or 0):
            ligne.quantite_livree_unites = int(ql_unites_calculee or 0)
            champs_a_maj.append("quantite_livree_unites")

    ligne.full_clean()

    if champs_a_maj:
        ligne.save(update_fields=champs_a_maj)


def _ensure_lignes_valides(req: Requisition) -> None:
    lignes = list(req.lignes.select_related("article"))
    if not lignes:
        raise ValueError("Réquisition invalide : aucune ligne d'article.")

    for ligne in lignes:
        _reparer_ligne_si_possible(ligne)

        if ligne.article_id is None:
            raise ValueError("Réquisition invalide : ligne sans article.")

        if ligne.quantite_demandee is None or int(ligne.quantite_demandee) <= 0:
            raise ValueError("Réquisition invalide : quantité demandée manquante ou invalide.")

        if int(ligne.quantite_demandee_unites or 0) <= 0:
            raise ValueError("Réquisition invalide : quantité demandée convertie invalide.")


@transaction.atomic
def creer_requisition(*, requisition: Requisition, lien_detail: str | None = None) -> Requisition:
    requisition.etat_requisition = Requisition.ETAT_EN_ATTENTE

    _ensure_lignes_valides(requisition)

    if requisition.directeur_direction_id is None:
        directeur = trouver_directeur_de_direction(direction=requisition.direction_demandeuse)
        requisition.directeur_direction = directeur

    requisition.full_clean()
    requisition.save(update_fields=["etat_requisition", "directeur_direction"])

    if requisition.directeur_direction_id:
        _notify_one(
            destinataire=requisition.directeur_direction,
            titre=f"Réquisition REQ-{requisition.id} à confirmer",
            message=(
                f"Une nouvelle réquisition REQ-{requisition.id} a été soumise par {requisition.soumetteur.email}.\n"
                f"Direction : {requisition.direction_demandeuse}\n"
                f"Merci de la confirmer."
            ),
            requisition=requisition,
            lien=lien_detail,
        )

    return requisition


@transaction.atomic
def valider_par_directeur_direction(
    *,
    requisition: Requisition,
    directeur,
    lien_detail: str | None = None,
) -> Requisition:
    req = _lock_requisition(requisition.pk)

    _ensure_lignes_valides(req)
    _ensure_etat(req, Requisition.ETAT_EN_ATTENTE)

    req.directeur_direction = directeur
    req.etat_requisition = Requisition.ETAT_VALIDEE
    req.date_approbation = timezone.now()
    req.full_clean()
    req.save(update_fields=["directeur_direction", "etat_requisition", "date_approbation"])

    _notify_one(
        destinataire=req.soumetteur,
        titre=f"Réquisition REQ-{req.id} confirmée",
        message=(
            f"Votre réquisition REQ-{req.id} a été confirmée par le Directeur de direction.\n"
            f"Elle est maintenant visible pour le Gestionnaire des ressources matérielles."
        ),
        requisition=req,
        lien=lien_detail,
    )

    gestionnaires = _utilisateurs_actifs_par_role(ROLE_GESTIONNAIRE)
    _notify_many(
        destinataires=gestionnaires,
        titre=f"Réquisition REQ-{req.id} à traiter",
        message=(
            f"Réquisition REQ-{req.id} confirmée.\n"
            f"Direction : {req.direction_demandeuse}\n"
            f"Veuillez la traiter."
        ),
        requisition=req,
        lien=lien_detail,
    )

    return req


@transaction.atomic
def demander_modification(
    *,
    requisition: Requisition,
    acteur,
    motif: str,
    lien_detail: str | None = None,
) -> Requisition:
    req = _lock_requisition(requisition.pk)

    _ensure_lignes_valides(req)

    if req.etat_requisition in {Requisition.ETAT_TRAITEE, Requisition.ETAT_REJETEE}:
        raise ValueError("Action refusée : réquisition clôturée (Traité/Rejeté).")

    req.etat_requisition = Requisition.ETAT_EN_ATTENTE_MODIF
    req.demande_modification_motif = (motif or "").strip()
    req.demande_modification_par = acteur
    req.date_demande_modification = timezone.now()
    req.full_clean()
    req.save(
        update_fields=[
            "etat_requisition",
            "demande_modification_motif",
            "demande_modification_par",
            "date_demande_modification",
        ]
    )

    _notify_one(
        destinataire=req.soumetteur,
        titre=f"Modification demandée — REQ-{req.id}",
        message=(
            f"Une modification a été demandée pour la réquisition REQ-{req.id}.\n"
            f"Motif : {req.demande_modification_motif}"
        ),
        requisition=req,
        lien=lien_detail,
    )

    return req


@transaction.atomic
def secretaire_apres_modification(*, requisition: Requisition) -> Requisition:
    req = _lock_requisition(requisition.pk)

    if req.etat_requisition in {Requisition.ETAT_TRAITEE, Requisition.ETAT_REJETEE}:
        raise ValueError("Action refusée : réquisition clôturée (Traité/Rejeté).")

    _ensure_lignes_valides(req)

    req.etat_requisition = Requisition.ETAT_EN_ATTENTE
    req.full_clean()
    req.save(update_fields=["etat_requisition"])
    return req


@transaction.atomic
def transferer_vers_directeur_daa(
    *,
    requisition: Requisition,
    gestionnaire,
    directeur_daa,
    lien_detail: str | None = None,
) -> Requisition:
    req = _lock_requisition(requisition.pk)

    _ensure_lignes_valides(req)
    _ensure_etat(req, Requisition.ETAT_VALIDEE)

    if req.transferee_vers_directeur_daa:
        raise ValueError("Action refusée : déjà transférée au Directeur DAA.")

    req.transferee_vers_directeur_daa = True
    req.directeur_daa = directeur_daa
    req.date_transfert_directeur_daa = timezone.now()
    req.full_clean()
    req.save(
        update_fields=[
            "transferee_vers_directeur_daa",
            "directeur_daa",
            "date_transfert_directeur_daa",
        ]
    )

    _notify_one(
        destinataire=directeur_daa,
        titre=f"Réquisition REQ-{req.id} transférée (DAA)",
        message=(
            f"Une réquisition a été transférée pour décision.\n"
            f"REQ-{req.id} • Direction : {req.direction_demandeuse}"
        ),
        requisition=req,
        lien=lien_detail,
    )

    _notify_one(
        destinataire=req.soumetteur,
        titre=f"Réquisition REQ-{req.id} transférée au Directeur DAA",
        message="Votre réquisition a été transférée au Directeur DAA pour décision.",
        requisition=req,
        lien=lien_detail,
    )

    return req


@transaction.atomic
def valider_par_directeur_daa(
    *,
    requisition: Requisition,
    directeur_daa,
    lien_detail: str | None = None,
) -> Requisition:
    req = _lock_requisition(requisition.pk)

    _ensure_lignes_valides(req)

    if not req.transferee_vers_directeur_daa or req.directeur_daa_id != directeur_daa.id:
        raise ValueError("Action refusée : réquisition non transférée à ce Directeur DAA.")

    if req.etat_requisition in {Requisition.ETAT_REJETEE, Requisition.ETAT_TRAITEE}:
        raise ValueError("Action refusée : réquisition clôturée (Traité/Rejeté).")

    if getattr(req, "sceau_directeur_daa", None):
        if str(req.sceau_directeur_daa).strip():
            raise ValueError("Action refusée : déjà confirmée (sceau DAA déjà présent).")

    req.directeur_daa = directeur_daa
    req.generer_sceau_daa()
    req.full_clean()
    req.save(update_fields=["directeur_daa", "sceau_directeur_daa", "date_sceau_directeur_daa"])

    _notify_one(
        destinataire=req.soumetteur,
        titre=f"Réquisition REQ-{req.id} confirmée (DAA)",
        message="Le Directeur DAA a confirmé votre réquisition.",
        requisition=req,
        lien=lien_detail,
    )

    gestionnaires = _utilisateurs_actifs_par_role(ROLE_GESTIONNAIRE)
    _notify_many(
        destinataires=gestionnaires,
        titre=f"Réquisition REQ-{req.id} confirmée (DAA)",
        message="Le Directeur DAA a confirmé la réquisition.",
        requisition=req,
        lien=lien_detail,
    )

    return req


@transaction.atomic
def rejeter_par_directeur_daa(
    *,
    requisition: Requisition,
    directeur_daa,
    motif: str = "",
    lien_detail: str | None = None,
) -> Requisition:
    req = _lock_requisition(requisition.pk)

    _ensure_lignes_valides(req)

    if not req.transferee_vers_directeur_daa or req.directeur_daa_id != directeur_daa.id:
        raise ValueError("Action refusée : réquisition non transférée à ce Directeur DAA.")

    if req.etat_requisition == Requisition.ETAT_TRAITEE:
        raise ValueError("Action refusée : déjà traitée.")

    req.directeur_daa = directeur_daa
    req.etat_requisition = Requisition.ETAT_REJETEE
    req.remarque = (motif or "").strip()
    req.full_clean()
    req.save(update_fields=["directeur_daa", "etat_requisition", "remarque"])

    _notify_one(
        destinataire=req.soumetteur,
        titre=f"Réquisition REQ-{req.id} rejetée (DAA)",
        message=f"Votre réquisition a été rejetée.\nMotif : {req.remarque or '—'}",
        requisition=req,
        lien=lien_detail,
    )

    gestionnaires = _utilisateurs_actifs_par_role(ROLE_GESTIONNAIRE)
    _notify_many(
        destinataires=gestionnaires,
        titre=f"Réquisition REQ-{req.id} rejetée (DAA)",
        message="Le Directeur DAA a rejeté la réquisition.",
        requisition=req,
        lien=lien_detail,
    )

    return req


@transaction.atomic
def traiter_requisition(
    *,
    requisition: Requisition,
    gestionnaire,
    quantites_livrees: Dict[int, Dict[str, Any]],
    lien_detail: str | None = None,
) -> Requisition:
    req = _lock_requisition(requisition.pk)

    _ensure_lignes_valides(req)
    _ensure_etat(req, Requisition.ETAT_VALIDEE)

    if req.etat_requisition == Requisition.ETAT_TRAITEE:
        raise ValueError("Action refusée : réquisition déjà traitée.")

    total_livre_unites = 0

    for ligne in req.lignes.select_related("article"):
        payload = quantites_livrees.get(ligne.id, {}) or {}

        try:
            qte = int(payload.get("quantite", 0) or 0)
        except (TypeError, ValueError):
            qte = 0

        unite_livree = _normaliser_libelle_unite(
            (payload.get("unite") or "").strip() or ligne.unite_demandee or "Unité"
        )

        if qte < 0:
            raise ValueError(f"Quantité livrée invalide pour l'article '{ligne.article}'.")

        if qte == 0:
            ligne.unite_livree = ""
            ligne.quantite_livree = 0
            ligne.quantite_livree_unites = 0
            ligne.full_clean()
            ligne.save(update_fields=["unite_livree", "quantite_livree", "quantite_livree_unites"])
            continue

        try:
            qte_unites = ligne.article.convertir_vers_unites_base(qte, unite_livree)
        except ValidationError as exc:
            raise ValueError(f"{ligne.article.nom} : {exc.messages[0]}")

        if qte_unites > int(ligne.quantite_demandee_unites or 0):
            raise ValueError(
                f"La quantité livrée pour '{ligne.article.nom}' ne peut pas dépasser la quantité demandée."
            )

        if qte_unites > int(ligne.article.stock_actuel or 0):
            raise ValueError(
                f"Stock insuffisant pour '{ligne.article.nom}'. Disponibilité actuelle : {ligne.article.stock_actuel_affichage}."
            )

        ligne.unite_livree = unite_livree
        ligne.quantite_livree = qte
        ligne.quantite_livree_unites = qte_unites
        ligne.full_clean()
        ligne.save(update_fields=["unite_livree", "quantite_livree", "quantite_livree_unites"])

        from mouvements_stock.services import enregistrer_sortie_stock

        enregistrer_sortie_stock(
            article=ligne.article,
            quantite=qte_unites,
            requisition=req,
        )
        total_livre_unites += qte_unites

    if total_livre_unites <= 0:
        raise ValueError("Impossible de traiter la réquisition : aucune quantité livrée n'a été saisie.")

    req.etat_requisition = Requisition.ETAT_TRAITEE
    req.traitee_par = gestionnaire
    req.date_livraison = timezone.now()
    req.recue_par = None
    req.date_reception = None
    req.full_clean()
    req.save(
        update_fields=[
            "etat_requisition",
            "traitee_par",
            "date_livraison",
            "recue_par",
            "date_reception",
        ]
    )

    _notify_one(
        destinataire=req.soumetteur,
        titre=f"Réquisition REQ-{req.id} traitée",
        message=(
            f"Votre réquisition REQ-{req.id} a été traitée par le gestionnaire.\n"
            f"Vous pouvez maintenant accuser réception."
        ),
        requisition=req,
        lien=lien_detail,
    )

    return req


@transaction.atomic
def accuser_reception(
    *,
    requisition: Requisition,
    secretaire,
    lien_detail: str | None = None,
) -> Requisition:
    req = _lock_requisition(requisition.pk)

    if req.soumetteur_id != secretaire.id:
        raise ValueError("Action refusée : seule la secrétaire demandeuse peut accuser réception.")

    if req.etat_requisition != Requisition.ETAT_TRAITEE:
        raise ValueError("Accusé de réception impossible : la réquisition n'est pas encore traitée.")

    if req.date_livraison is None or req.traitee_par_id is None:
        raise ValueError("Accusé de réception impossible : le traitement n'est pas complètement enregistré.")

    if req.date_reception is not None or req.recue_par_id is not None:
        raise ValueError("La réception a déjà été confirmée pour cette réquisition.")

    _ensure_lignes_valides(req)

    req.recue_par = secretaire
    req.date_reception = timezone.now()
    req.full_clean()
    req.save(update_fields=["recue_par", "date_reception"])

    if req.traitee_par_id:
        _notify_one(
            destinataire=req.traitee_par,
            titre=f"Réception confirmée — REQ-{req.id}",
            message=f"La secrétaire a accusé réception de la réquisition REQ-{req.id}.",
            requisition=req,
            lien=lien_detail,
        )

    return req