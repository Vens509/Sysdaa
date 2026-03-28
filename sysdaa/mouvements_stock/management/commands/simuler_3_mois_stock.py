from __future__ import annotations

import calendar
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from articles.models import Article
from audit.models import AuditLog
from audit.services import enregistrer_audit
from core.permissions import ROLE_DIRECTEUR_DAA, ROLE_GESTIONNAIRE, ROLE_SECRETAIRE
from mouvements_stock.models import MouvementStock
from mouvements_stock.services import enregistrer_entree_stock, enregistrer_sortie_stock
from requisitions.models import LigneRequisition, Requisition
from utilisateurs.models import Utilisateur


MOTIFS_MANUELS_STANDARDS = [
    "Périmé",
    "Endommagé",
    "Sorti pour un travail",
]

MOTIFS_MANUELS_AUTRES = [
    "Transfert interne vers la salle de réunion",
    "Remis pour démonstration technique",
    "Prêt temporaire au service maintenance",
    "Utilisé pour préparation logistique",
    "Réaffecté à un poste de travail",
]

MOTIFS_REQUISITION = [
    "Besoins mensuels de fonctionnement",
    "Renouvellement du stock de bureau",
    "Appui logistique à une activité interne",
    "Approvisionnement courant du service",
    "Besoins de consommation régulière",
]


@dataclass(slots=True)
class OperationStock:
    quantite_operation: int
    conditionnement: str
    qpc: int
    quantite_unites: int


class Command(BaseCommand):
    help = (
        "Simule 3 mois de fonctionnement du stock (janvier, février, mars) "
        "avec entrées, sorties manuelles et sorties sur réquisitions, "
        "en gardant une cohérence mensuelle du stock."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--annee",
            type=int,
            default=2026,
            help="Année de simulation. Défaut : 2026.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=20260328,
            help="Seed pseudo-aléatoire pour obtenir toujours la même simulation.",
        )
        parser.add_argument(
            "--limit-articles",
            type=int,
            default=0,
            help="Limiter le nombre d'articles simulés. 0 = tous les articles.",
        )
        parser.add_argument(
            "--reset-simulation",
            action="store_true",
            help="Supprime d'abord les données créées par une précédente simulation de la même année.",
        )

    def handle(self, *args, **options):
        annee = int(options["annee"])
        seed = int(options["seed"])
        limit_articles = int(options["limit_articles"] or 0)
        reset_simulation = bool(options["reset_simulation"])

        self.rng = random.Random(seed)
        self.simulation_tag = f"SIM-STOCK-JFM-{annee}"

        gestionnaire = self._resolve_acteur_stock()
        secretaires = self._resolve_secretaires()
        if not secretaires:
            raise CommandError(
                "Aucune secrétaire active avec direction affectée n'a été trouvée."
            )

        directeurs_by_direction = self._resolve_directeurs_by_direction()

        articles_qs = Article.objects.select_related("categorie", "utilisateur_enregistreur").order_by("categorie__libelle", "nom")
        articles = list(articles_qs[:limit_articles] if limit_articles > 0 else articles_qs)

        if not articles:
            raise CommandError("Aucun article trouvé en base.")

        if reset_simulation:
            self._reset_previous_simulation(annee)

        groups = self._build_target_groups(articles)

        counters = {
            "articles": 0,
            "stock_minimal_maj": 0,
            "entrees": 0,
            "sorties_manuelles": 0,
            "sorties_requisitions": 0,
            "requisitions": 0,
            "ruptures_finales": 0,
            "alertes_oranges_finales": 0,
            "stocks_ok_finaux": 0,
        }

        with transaction.atomic():
            for index, article in enumerate(articles, start=1):
                counters["articles"] += 1
                statut_cible = groups[article.pk]

                if self._prepare_article_threshold(article):
                    counters["stock_minimal_maj"] += 1

                initial_units = self._compute_initial_units(article, statut_cible)
                opening_dt = self._dt(annee, 1, 2, 9, minute=(index % 6) * 10)
                self._create_entry(article, initial_units, opening_dt, gestionnaire, counters)

                for mois in (1, 2, 3):
                    self._simulate_month(
                        article=article,
                        annee=annee,
                        mois=mois,
                        secretaires=secretaires,
                        directeurs_by_direction=directeurs_by_direction,
                        gestionnaire=gestionnaire,
                        counters=counters,
                    )

                target_final = self._compute_target_final_stock(article, statut_cible)
                self._adjust_march_final_stock(
                    article=article,
                    annee=annee,
                    target_final=target_final,
                    gestionnaire=gestionnaire,
                    counters=counters,
                )

                article.refresh_from_db(fields=["stock_actuel", "stock_initial", "stock_minimal"])
                if article.stock_actuel == 0:
                    counters["ruptures_finales"] += 1
                elif article.stock_actuel < article.stock_minimal:
                    counters["alertes_oranges_finales"] += 1
                else:
                    counters["stocks_ok_finaux"] += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Simulation terminée : {self.simulation_tag}"))
        self.stdout.write(f"Articles simulés : {counters['articles']}")
        self.stdout.write(f"Stock minimal mis à jour : {counters['stock_minimal_maj']}")
        self.stdout.write(f"Entrées créées : {counters['entrees']}")
        self.stdout.write(f"Sorties manuelles créées : {counters['sorties_manuelles']}")
        self.stdout.write(f"Réquisitions traitées créées : {counters['requisitions']}")
        self.stdout.write(f"Sorties liées aux réquisitions : {counters['sorties_requisitions']}")
        self.stdout.write(f"Articles en rupture finale : {counters['ruptures_finales']}")
        self.stdout.write(f"Articles en alerte orange finale : {counters['alertes_oranges_finales']}")
        self.stdout.write(f"Articles OK en fin mars : {counters['stocks_ok_finaux']}")

    def _resolve_acteur_stock(self) -> Utilisateur:
        gestionnaire = (
            Utilisateur.objects.filter(
                role__nom_role=ROLE_GESTIONNAIRE,
                statut=Utilisateur.STATUT_ACTIF,
                is_active=True,
            )
            .select_related("role", "direction_affectee")
            .order_by("id")
            .first()
        )
        if gestionnaire:
            return gestionnaire

        directeur_daa = (
            Utilisateur.objects.filter(
                role__nom_role=ROLE_DIRECTEUR_DAA,
                statut=Utilisateur.STATUT_ACTIF,
                is_active=True,
            )
            .select_related("role", "direction_affectee")
            .order_by("id")
            .first()
        )
        if directeur_daa:
            return directeur_daa

        raise CommandError(
            "Aucun acteur actif trouvé pour enregistrer les mouvements de stock. "
            "Il faut au moins un Gestionnaire des ressources matérielles ou un Directeur DAA actif."
        )

    def _resolve_secretaires(self) -> list[Utilisateur]:
        return list(
            Utilisateur.objects.filter(
                role__nom_role=ROLE_SECRETAIRE,
                statut=Utilisateur.STATUT_ACTIF,
                is_active=True,
                direction_affectee__isnull=False,
            )
            .select_related("direction_affectee", "role")
            .order_by("direction_affectee__nom", "nom", "prenom", "id")
        )

    def _resolve_directeurs_by_direction(self) -> dict[int, Utilisateur]:
        qs = (
            Utilisateur.objects.filter(
                is_directeur_direction=True,
                statut=Utilisateur.STATUT_ACTIF,
                is_active=True,
                direction_affectee__isnull=False,
            )
            .select_related("direction_affectee", "role")
            .order_by("id")
        )
        return {u.direction_affectee_id: u for u in qs}

    def _build_target_groups(self, articles: list[Article]) -> dict[int, str]:
        article_ids = [a.pk for a in articles]
        self.rng.shuffle(article_ids)
        total = len(article_ids)

        nb_rupture = max(1, round(total * 0.12)) if total >= 6 else max(1, total // 4)
        nb_orange = max(1, round(total * 0.18)) if total >= 6 else max(1, total // 3)

        groups: dict[int, str] = {}
        rupture_ids = set(article_ids[:nb_rupture])
        orange_ids = set(article_ids[nb_rupture : nb_rupture + nb_orange])

        for article in articles:
            if article.pk in rupture_ids:
                groups[article.pk] = "rupture"
            elif article.pk in orange_ids:
                groups[article.pk] = "orange"
            else:
                groups[article.pk] = "ok"
        return groups

    def _prepare_article_threshold(self, article: Article) -> bool:
        article.refresh_from_db(fields=["stock_minimal", "quantite_par_conditionnement"])
        if int(article.stock_minimal or 0) > 0:
            return False

        qpc = max(1, int(article.quantite_par_conditionnement or 1))
        base = self.rng.randint(8, 28)
        if qpc > 1:
            base = max(base, qpc * self.rng.randint(2, 4))

        article.stock_minimal = base
        article.full_clean()
        article.save(update_fields=["stock_minimal"])
        return True

    def _compute_initial_units(self, article: Article, statut_cible: str) -> int:
        seuil = max(1, int(article.stock_minimal or 1))
        if statut_cible == "rupture":
            return max(seuil * self.rng.randint(2, 4), self.rng.randint(seuil + 8, seuil * 5))
        if statut_cible == "orange":
            return max(seuil * self.rng.randint(3, 5), self.rng.randint(seuil + 12, seuil * 6))
        return max(seuil * self.rng.randint(4, 7), self.rng.randint(seuil + 20, seuil * 8))

    def _compute_target_final_stock(self, article: Article, statut_cible: str) -> int:
        seuil = max(1, int(article.stock_minimal or 1))
        if statut_cible == "rupture":
            return 0
        if statut_cible == "orange":
            return self.rng.randint(1, max(1, seuil - 1))
        return self.rng.randint(seuil + 1, max(seuil + 2, seuil * 3))

    def _simulate_month(
        self,
        *,
        article: Article,
        annee: int,
        mois: int,
        secretaires: list[Utilisateur],
        directeurs_by_direction: dict[int, Utilisateur],
        gestionnaire: Utilisateur,
        counters: dict[str, int],
    ) -> None:
        article.refresh_from_db(fields=["stock_actuel", "stock_minimal"])
        stock = int(article.stock_actuel or 0)
        seuil = max(1, int(article.stock_minimal or 1))
        month_last_day = calendar.monthrange(annee, mois)[1]

        needs_entry = (
            mois == 2 and stock <= seuil * 2
        ) or (
            mois == 3 and stock <= seuil * 2
        ) or (
            self.rng.random() < (0.35 if mois == 1 else 0.55)
        )

        if needs_entry:
            entry_units = self.rng.randint(max(5, seuil), max(seuil + 6, seuil * 3))
            if mois == 1:
                entry_day = min(8, month_last_day)
            elif mois == 2:
                entry_day = min(6, month_last_day)
            else:
                entry_day = min(7, month_last_day)
            self._create_entry(
                article,
                entry_units,
                self._dt(annee, mois, entry_day, 9, minute=self.rng.choice([0, 15, 30, 45])),
                gestionnaire,
                counters,
            )

        article.refresh_from_db(fields=["stock_actuel", "stock_minimal"])
        stock = int(article.stock_actuel or 0)
        if stock <= 0:
            return

        # 1 à 2 réquisitions réalistes si le stock le permet.
        nb_requisitions = 1 if self.rng.random() < 0.65 else 0
        if mois in (2, 3) and stock > seuil * 2 and self.rng.random() < 0.35:
            nb_requisitions += 1

        for _ in range(nb_requisitions):
            article.refresh_from_db(fields=["stock_actuel", "stock_minimal"])
            stock = int(article.stock_actuel or 0)
            if stock <= 0:
                break

            max_units = max(1, min(stock, max(4, seuil * 2)))
            delivered_units = self.rng.randint(1, max_units)
            if delivered_units <= 0:
                continue

            secretary = self.rng.choice(secretaires)
            directeur = directeurs_by_direction.get(secretary.direction_affectee_id)
            prep_day = self.rng.randint(3, max(3, month_last_day - 5))
            prep_dt = self._dt(annee, mois, prep_day, 10, minute=self.rng.choice([0, 20, 40]))
            approve_dt = prep_dt + timedelta(hours=2)
            deliver_dt = prep_dt + timedelta(days=1, hours=3)
            receive_dt = deliver_dt + timedelta(days=1, hours=1)

            self._create_requisition_with_stock_output(
                article=article,
                secretary=secretary,
                directeur_direction=directeur,
                gestionnaire=gestionnaire,
                date_preparation=prep_dt,
                date_approbation=approve_dt,
                date_livraison=deliver_dt,
                date_reception=receive_dt,
                delivered_units=delivered_units,
                counters=counters,
            )

        article.refresh_from_db(fields=["stock_actuel", "stock_minimal"])
        stock = int(article.stock_actuel or 0)
        if stock <= 0:
            return

        # 0 à 1 sortie manuelle pour varier les rapports.
        if self.rng.random() < 0.58:
            stock = int(article.stock_actuel or 0)
            max_units = max(1, min(stock, max(2, seuil)))
            manual_units = self.rng.randint(1, max_units)
            manual_day = self.rng.randint(6, max(6, month_last_day - 1))
            manual_dt = self._dt(annee, mois, manual_day, 15, minute=self.rng.choice([0, 10, 20, 30, 40, 50]))
            self._create_manual_output(
                article=article,
                units=manual_units,
                date_mouvement=manual_dt,
                acteur=gestionnaire,
                counters=counters,
            )

    def _adjust_march_final_stock(
        self,
        *,
        article: Article,
        annee: int,
        target_final: int,
        gestionnaire: Utilisateur,
        counters: dict[str, int],
    ) -> None:
        article.refresh_from_db(fields=["stock_actuel"])
        current_stock = int(article.stock_actuel or 0)

        if current_stock == target_final:
            return

        if current_stock < target_final:
            diff = target_final - current_stock
            self._create_entry(
                article,
                diff,
                self._dt(annee, 3, 28, 9, minute=self.rng.choice([0, 15, 30, 45])),
                gestionnaire,
                counters,
            )
            return

        diff = current_stock - target_final
        self._create_manual_output(
            article=article,
            units=diff,
            date_mouvement=self._dt(annee, 3, 30, 16, minute=self.rng.choice([0, 10, 20, 30, 40, 50])),
            acteur=gestionnaire,
            counters=counters,
            forced_motif="Périmé" if target_final == 0 else "Sorti pour un travail",
        )

    def _create_entry(
        self,
        article: Article,
        units: int,
        date_mouvement,
        acteur: Utilisateur,
        counters: dict[str, int],
    ) -> None:
        op = self._units_to_operation(article, units, prefer_packaging=True)
        stock_avant = int(article.stock_actuel or 0)
        result = enregistrer_entree_stock(
            article=article,
            quantite=op.quantite_operation,
            conditionnement_mouvement=op.conditionnement,
            quantite_par_conditionnement_mouvement=(None if op.conditionnement == article.unite else op.qpc),
            date_mouvement=date_mouvement,
            acteur=acteur,
        )
        counters["entrees"] += 1

        self._log_movement_audit(
            mouvement_id=result.mouvement_id,
            acteur=acteur,
            article=article,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE,
            quantite=op.quantite_operation,
            quantite_unites=op.quantite_unites,
            stock_avant=stock_avant,
            stock_apres=result.nouveau_stock,
            date_mouvement=date_mouvement,
            origine="simulation_entree",
            conditionnement=op.conditionnement,
            qpc=op.qpc,
            motif_sortie="",
        )

    def _create_manual_output(
        self,
        *,
        article: Article,
        units: int,
        date_mouvement,
        acteur: Utilisateur,
        counters: dict[str, int],
        forced_motif: str | None = None,
    ) -> None:
        article.refresh_from_db(fields=["stock_actuel"])
        stock_avant = int(article.stock_actuel or 0)
        units = max(1, min(int(units or 0), stock_avant))
        if units <= 0:
            return

        op = self._units_to_operation(article, units, prefer_packaging=True)
        motif = forced_motif or self._pick_manual_motif()

        result = enregistrer_sortie_stock(
            article=article,
            quantite=op.quantite_operation,
            motif_sortie=motif,
            requisition=None,
            conditionnement_mouvement=op.conditionnement,
            quantite_par_conditionnement_mouvement=(None if op.conditionnement == article.unite else op.qpc),
            date_mouvement=date_mouvement,
            acteur=acteur,
        )
        counters["sorties_manuelles"] += 1

        self._log_movement_audit(
            mouvement_id=result.mouvement_id,
            acteur=acteur,
            article=article,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            quantite=op.quantite_operation,
            quantite_unites=op.quantite_unites,
            stock_avant=stock_avant,
            stock_apres=result.nouveau_stock,
            date_mouvement=date_mouvement,
            origine="manuelle",
            conditionnement=op.conditionnement,
            qpc=op.qpc,
            motif_sortie=motif,
        )

    def _create_requisition_with_stock_output(
        self,
        *,
        article: Article,
        secretary: Utilisateur,
        directeur_direction: Utilisateur | None,
        gestionnaire: Utilisateur,
        date_preparation,
        date_approbation,
        date_livraison,
        date_reception,
        delivered_units: int,
        counters: dict[str, int],
    ) -> None:
        article.refresh_from_db(fields=["stock_actuel"])
        available = int(article.stock_actuel or 0)
        if available <= 0:
            return

        delivered_units = max(1, min(delivered_units, available))
        requested_units = delivered_units + self.rng.randint(0, max(1, delivered_units // 3))

        demanded = self._units_to_operation(article, requested_units, prefer_packaging=True)
        delivered = self._units_to_operation(article, delivered_units, prefer_packaging=True)

        req = Requisition(
            date_preparation=date_preparation,
            etat_requisition=Requisition.ETAT_TRAITEE,
            motif_global=self.rng.choice(MOTIFS_REQUISITION),
            remarque=f"[{self.simulation_tag}] Réquisition simulée pour données de test.",
            date_approbation=date_approbation,
            date_livraison=date_livraison,
            date_reception=date_reception,
            soumetteur=secretary,
            directeur_direction=directeur_direction,
            transferee_vers_directeur_daa=False,
            directeur_daa=None,
            traitee_par=gestionnaire,
            recue_par=secretary,
        )
        req.full_clean()
        req.save()

        ligne = LigneRequisition(
            requisition=req,
            article=article,
            unite_demandee=demanded.conditionnement,
            quantite_demandee=demanded.quantite_operation,
            quantite_demandee_unites=demanded.quantite_unites,
            unite_livree=delivered.conditionnement,
            quantite_livree=delivered.quantite_operation,
            quantite_livree_unites=delivered.quantite_unites,
            motif_article="Simulation de consommation normale du service.",
        )
        ligne.full_clean()
        ligne.save()

        stock_avant = int(article.stock_actuel or 0)
        result = enregistrer_sortie_stock(
            article=article,
            quantite=delivered.quantite_operation,
            motif_sortie="",
            requisition=req,
            conditionnement_mouvement=delivered.conditionnement,
            quantite_par_conditionnement_mouvement=(None if delivered.conditionnement == article.unite else delivered.qpc),
            date_mouvement=date_livraison,
            acteur=gestionnaire,
        )

        counters["requisitions"] += 1
        counters["sorties_requisitions"] += 1

        enregistrer_audit(
            action=AuditLog.Action.CREATION,
            acteur=gestionnaire,
            app_label="requisitions",
            cible=req,
            message="Création d'une réquisition simulée traitée.",
            details={
                "simulation_tag": self.simulation_tag,
                "origine": "simulation_requisition",
                "article_id": article.pk,
                "article_nom": article.nom,
                "ligne_id": ligne.pk,
                "mouvement_id": result.mouvement_id,
                "quantite_demandee_unites": demanded.quantite_unites,
                "quantite_livree_unites": delivered.quantite_unites,
            },
        )

        self._log_movement_audit(
            mouvement_id=result.mouvement_id,
            acteur=gestionnaire,
            article=article,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            quantite=delivered.quantite_operation,
            quantite_unites=delivered.quantite_unites,
            stock_avant=stock_avant,
            stock_apres=result.nouveau_stock,
            date_mouvement=date_livraison,
            origine="requisition",
            conditionnement=delivered.conditionnement,
            qpc=delivered.qpc,
            motif_sortie="",
            requisition=req,
        )

    def _units_to_operation(self, article: Article, units: int, *, prefer_packaging: bool) -> OperationStock:
        units = int(units or 0)
        qpc = max(1, int(article.quantite_par_conditionnement or 1))
        unite = (article.unite or "Unité").strip() or "Unité"

        if units <= 0:
            raise ValueError("La quantité en unités doit être > 0.")

        if prefer_packaging and qpc > 1 and units % qpc == 0 and self.rng.random() < 0.75:
            return OperationStock(
                quantite_operation=units // qpc,
                conditionnement=unite,
                qpc=qpc,
                quantite_unites=units,
            )

        return OperationStock(
            quantite_operation=units,
            conditionnement="Unité",
            qpc=1,
            quantite_unites=units,
        )

    def _pick_manual_motif(self) -> str:
        if self.rng.random() < 0.72:
            return self.rng.choice(MOTIFS_MANUELS_STANDARDS)
        return self.rng.choice(MOTIFS_MANUELS_AUTRES)

    def _log_movement_audit(
        self,
        *,
        mouvement_id: int,
        acteur: Utilisateur,
        article: Article,
        type_mouvement: str,
        quantite: int,
        quantite_unites: int,
        stock_avant: int,
        stock_apres: int,
        date_mouvement,
        origine: str,
        conditionnement: str,
        qpc: int,
        motif_sortie: str,
        requisition: Requisition | None = None,
    ) -> None:
        label = "Entrée stock" if type_mouvement == MouvementStock.TypeMouvement.ENTREE else "Sortie stock"
        enregistrer_audit(
            action=AuditLog.Action.CREATION,
            acteur=acteur,
            app_label="mouvements_stock",
            cible_type="MouvementStock",
            cible_id=str(mouvement_id),
            cible_label=f"{label} #{mouvement_id}",
            message=f"{label} simulée créée.",
            details={
                "simulation_tag": self.simulation_tag,
                "type_mouvement": type_mouvement,
                "mouvement_id": mouvement_id,
                "article_id": article.pk,
                "article_nom": article.nom,
                "quantite": quantite,
                "quantite_unites": quantite_unites,
                "conditionnement_mouvement": conditionnement,
                "quantite_par_conditionnement_mouvement": qpc,
                "stock_avant": stock_avant,
                "stock_apres": stock_apres,
                "motif_sortie": motif_sortie,
                "origine": origine,
                "date_mouvement": timezone.localtime(date_mouvement).isoformat(),
                "requisition_id": requisition.pk if requisition else None,
            },
        )

    def _reset_previous_simulation(self, annee: int) -> None:
        self.stdout.write(self.style.WARNING(f"Réinitialisation de la simulation {self.simulation_tag}..."))

        req_ids = list(
            Requisition.objects.filter(
                Q(remarque__icontains=self.simulation_tag) | Q(motif_global__icontains=self.simulation_tag),
                date_preparation__year=annee,
                date_preparation__month__in=[1, 2, 3],
            ).values_list("id", flat=True)
        )

        mouvement_ids_from_audit = list(
            AuditLog.objects.filter(
                app="mouvements_stock",
                action=AuditLog.Action.CREATION,
                details__simulation_tag=self.simulation_tag,
            ).values_list("cible_id", flat=True)
        )
        mouvement_ids = [int(mid) for mid in mouvement_ids_from_audit if str(mid).isdigit()]

        if req_ids:
            MouvementStock.objects.filter(requisition_id__in=req_ids).delete()
            Requisition.objects.filter(id__in=req_ids).delete()

        if mouvement_ids:
            MouvementStock.objects.filter(id__in=mouvement_ids).delete()

        AuditLog.objects.filter(details__simulation_tag=self.simulation_tag).delete()

    def _dt(self, annee: int, mois: int, jour: int, heure: int, minute: int = 0):
        naive = datetime(annee, mois, jour, heure, minute, 0)
        if timezone.is_naive(naive):
            return timezone.make_aware(naive, timezone.get_current_timezone())
        return naive
