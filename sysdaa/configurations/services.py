from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from django.db import IntegrityError, connection, transaction
from django.db.models import F
from django.utils import timezone

from .models import ClotureStockMensuelle, ConfigurationSysteme


ADVISORY_LOCK_KEY_1 = 941
ADVISORY_LOCK_KEY_2 = 3301

ADVISORY_LOCK_STOCK_KEY_1 = 941
ADVISORY_LOCK_STOCK_KEY_2 = 3302


@dataclass(frozen=True)
class AnneeFiscale:
    annee_debut: int
    annee_fin: int

    @property
    def code(self) -> str:
        return f"{self.annee_debut}-{self.annee_fin}"

    @property
    def label(self) -> str:
        return self.code

    @property
    def date_debut(self) -> date:
        return date(self.annee_debut, 10, 1)

    @property
    def date_fin(self) -> date:
        return date(self.annee_fin, 9, 30)


@dataclass(frozen=True)
class PeriodeMensuelle:
    annee: int
    mois: int

    @property
    def code(self) -> str:
        return f"{self.annee:04d}-{self.mois:02d}"

    @property
    def label(self) -> str:
        return f"{self.mois:02d}/{self.annee:04d}"


def _to_local_date(value=None) -> date:
    if value is None:
        return timezone.localdate()

    if isinstance(value, datetime):
        if timezone.is_aware(value):
            return timezone.localtime(value).date()
        return value.date()

    if isinstance(value, date):
        return value

    raise ValueError("Date invalide pour le calcul de l'année fiscale.")


def calculer_annee_fiscale_pour_date(value=None) -> AnneeFiscale:
    d = _to_local_date(value)

    if d.month >= 10:
        return AnneeFiscale(annee_debut=d.year, annee_fin=d.year + 1)

    return AnneeFiscale(annee_debut=d.year - 1, annee_fin=d.year)


def calculer_periode_mensuelle_pour_date(value=None) -> PeriodeMensuelle:
    d = _to_local_date(value)
    return PeriodeMensuelle(annee=d.year, mois=d.month)


def _configurateur_auto(configurateur):
    if configurateur is not None and getattr(configurateur, "is_authenticated", False):
        return configurateur
    return None


def _est_postgresql() -> bool:
    return connection.vendor == "postgresql"


def _acquerir_verrou_global_configuration() -> None:
    """
    Verrou transactionnel PostgreSQL.
    Tant que la transaction n'est pas terminée, une seule requête peut
    modifier la configuration fiscale.
    """
    if not _est_postgresql():
        return

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s, %s);",
            [ADVISORY_LOCK_KEY_1, ADVISORY_LOCK_KEY_2],
        )


def _acquerir_verrou_global_stock_mensuel() -> None:
    """
    Verrou transactionnel PostgreSQL pour la bascule mensuelle du stock.
    Il évite qu'une même période soit initialisée plusieurs fois
    en cas d'accès concurrents.
    """
    if not _est_postgresql():
        return

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s, %s);",
            [ADVISORY_LOCK_STOCK_KEY_1, ADVISORY_LOCK_STOCK_KEY_2],
        )


def get_configuration_active() -> ConfigurationSysteme | None:
    return (
        ConfigurationSysteme.objects.filter(est_active=True)
        .order_by("-annee_debut", "-id")
        .first()
    )


def lister_configurations():
    return ConfigurationSysteme.objects.order_by("-annee_debut", "-id")


def get_cloture_stock_mensuelle_pour_periode(*, annee: int, mois: int) -> ClotureStockMensuelle | None:
    return (
        ClotureStockMensuelle.objects.filter(annee=annee, mois=mois)
        .order_by("-id")
        .first()
    )


def get_derniere_cloture_stock_mensuelle() -> ClotureStockMensuelle | None:
    return (
        ClotureStockMensuelle.objects.order_by("-annee", "-mois", "-id")
        .first()
    )


def _annee_active_est_deja_correcte(af: AnneeFiscale) -> ConfigurationSysteme | None:
    cfg = get_configuration_active()
    if cfg is None:
        return None

    if cfg.annee_debut == af.annee_debut and cfg.annee_fin == af.annee_fin:
        return cfg

    return None


def _periode_stock_est_deja_initialisee(pm: PeriodeMensuelle) -> ClotureStockMensuelle | None:
    return (
        ClotureStockMensuelle.objects.filter(annee=pm.annee, mois=pm.mois)
        .order_by("-id")
        .first()
    )


@transaction.atomic
def assurer_annee_fiscale_active_pour_date(*, date_reference=None, configurateur=None) -> ConfigurationSysteme:
    """
    Version robuste à forte concurrence :
    - verrou transactionnel PostgreSQL
    - relecture après verrou
    - création si absente
    - activation de la bonne année
    - désactivation des autres
    """
    af = calculer_annee_fiscale_pour_date(date_reference)
    auto_configurateur = _configurateur_auto(configurateur)

    _acquerir_verrou_global_configuration()

    cfg_active = (
        ConfigurationSysteme.objects.select_for_update()
        .filter(est_active=True)
        .order_by("-annee_debut", "-id")
        .first()
    )

    if (
        cfg_active is not None
        and cfg_active.annee_debut == af.annee_debut
        and cfg_active.annee_fin == af.annee_fin
    ):
        if auto_configurateur is not None and cfg_active.configurateur_id is None:
            cfg_active.configurateur = auto_configurateur
            cfg_active.save(update_fields=["configurateur"])
        return cfg_active

    cfg_cible = (
        ConfigurationSysteme.objects.select_for_update()
        .filter(annee_debut=af.annee_debut, annee_fin=af.annee_fin)
        .first()
    )

    if cfg_cible is None:
        try:
            cfg_cible = ConfigurationSysteme.objects.create(
                annee_debut=af.annee_debut,
                annee_fin=af.annee_fin,
                est_active=True,
                configurateur=auto_configurateur,
            )
        except IntegrityError:
            cfg_cible = (
                ConfigurationSysteme.objects.select_for_update()
                .filter(annee_debut=af.annee_debut, annee_fin=af.annee_fin)
                .first()
            )

    if cfg_cible is None:
        raise RuntimeError("Impossible de charger ou créer la configuration fiscale cible.")

    ConfigurationSysteme.objects.filter(est_active=True).exclude(pk=cfg_cible.pk).update(est_active=False)

    champs_a_mettre_a_jour = []

    if not cfg_cible.est_active:
        cfg_cible.est_active = True
        champs_a_mettre_a_jour.append("est_active")

    if auto_configurateur is not None and cfg_cible.configurateur_id is None:
        cfg_cible.configurateur = auto_configurateur
        champs_a_mettre_a_jour.append("configurateur")

    if champs_a_mettre_a_jour:
        cfg_cible.save(update_fields=champs_a_mettre_a_jour)

    return cfg_cible


def assurer_annee_fiscale_active_auto(*, configurateur=None) -> ConfigurationSysteme:
    """
    Point d'entrée principal appelé par le middleware.
    Optimisation :
    - lecture simple d'abord
    - transaction + verrou seulement si nécessaire
    """
    af = calculer_annee_fiscale_pour_date()

    cfg_ok = _annee_active_est_deja_correcte(af)
    if cfg_ok is not None:
        return cfg_ok

    return assurer_annee_fiscale_active_pour_date(
        date_reference=af.date_debut,
        configurateur=configurateur,
    )


@transaction.atomic
def assurer_bascule_stock_mensuelle_pour_date(*, date_reference=None, configurateur=None) -> ClotureStockMensuelle:
    """
    Initialise UNE seule fois le stock de départ du mois courant.

    Règle métier appliquée :
    - au premier lancement de l'application dans un nouveau mois
    - stock_initial prend la valeur du stock_actuel
    - stock_actuel reste inchangé
    - une trace persistante est créée pour empêcher une double exécution
    """
    pm = calculer_periode_mensuelle_pour_date(date_reference)
    auto_configurateur = _configurateur_auto(configurateur)

    _acquerir_verrou_global_stock_mensuel()

    cloture_existante = (
        ClotureStockMensuelle.objects.select_for_update()
        .filter(annee=pm.annee, mois=pm.mois)
        .order_by("-id")
        .first()
    )

    if cloture_existante is not None:
        if auto_configurateur is not None and cloture_existante.configurateur_id is None:
            cloture_existante.configurateur = auto_configurateur
            cloture_existante.save(update_fields=["configurateur"])
        return cloture_existante

    assurer_annee_fiscale_active_pour_date(
        date_reference=_to_local_date(date_reference),
        configurateur=auto_configurateur,
    )

    from articles.models import Article

    articles_qs = Article.objects.select_for_update().all()

    nombre_articles_total = articles_qs.count()
    nombre_articles_mis_a_jour = articles_qs.exclude(
        stock_initial=F("stock_actuel")
    ).update(stock_initial=F("stock_actuel"))

    try:
        cloture = ClotureStockMensuelle.objects.create(
            annee=pm.annee,
            mois=pm.mois,
            nombre_articles_total=nombre_articles_total,
            nombre_articles_mis_a_jour=nombre_articles_mis_a_jour,
            configurateur=auto_configurateur,
        )
    except IntegrityError:
        cloture = (
            ClotureStockMensuelle.objects.select_for_update()
            .filter(annee=pm.annee, mois=pm.mois)
            .order_by("-id")
            .first()
        )

    if cloture is None:
        raise RuntimeError("Impossible de charger ou créer la clôture mensuelle du stock.")

    return cloture


def assurer_bascule_stock_mensuelle_auto(*, configurateur=None) -> ClotureStockMensuelle:
    """
    Point d'entrée principal appelé par le middleware.
    Optimisation :
    - lecture simple d'abord
    - transaction + verrou seulement si nécessaire
    """
    pm = calculer_periode_mensuelle_pour_date()

    cloture_ok = _periode_stock_est_deja_initialisee(pm)
    if cloture_ok is not None:
        return cloture_ok

    return assurer_bascule_stock_mensuelle_pour_date(
        date_reference=timezone.localdate(),
        configurateur=configurateur,
    )


def get_annee_fiscale_active_auto() -> AnneeFiscale:
    cfg = assurer_annee_fiscale_active_auto()
    return AnneeFiscale(
        annee_debut=cfg.annee_debut,
        annee_fin=cfg.annee_fin,
    )
