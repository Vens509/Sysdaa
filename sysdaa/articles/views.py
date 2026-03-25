from __future__ import annotations

from typing import Iterable

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from audit.models import AuditLog
from audit.services import audit_log as enregistrer_audit
from fournisseurs.models import ArticleFournisseur, Fournisseur

from .forms import ArticleForm, CategorieForm
from .models import Article, Categorie, _normaliser_libelle_unite
from .permissions import articles_required


UNITES_STANDARD = {
    "Unité",
    "Boîte",
    "Paquet",
    "Carton",
    "Caisse",
    "Ramette",
    "Rame",
    "Douzaine",
    "Sac",
    "Bidon",
    "Bouteille",
    "Flacon",
    "Lot",
}


ARTICLES_PAR_PAGE = 10


def _normaliser_texte(value: str) -> str:
    return (value or "").strip()


def _get_or_create_categorie(libelle: str) -> tuple[Categorie, bool]:
    libelle = _normaliser_texte(libelle)

    categorie_existante = Categorie.objects.filter(libelle__iexact=libelle).first()
    if categorie_existante:
        return categorie_existante, False

    return Categorie.objects.create(libelle=libelle), True


def _get_or_create_fournisseur(nom: str) -> tuple[Fournisseur, bool]:
    nom = _normaliser_texte(nom)

    fournisseur_existant = Fournisseur.objects.filter(nom__iexact=nom).first()
    if fournisseur_existant:
        return fournisseur_existant, False

    return Fournisseur.objects.create(nom=nom), True


def _collecter_fournisseurs_depuis_form(
    form: ArticleForm,
) -> tuple[list[Fournisseur], list[str]]:
    fournisseurs_selectionnes = list(form.cleaned_data.get("fournisseurs") or [])
    fournisseurs_nouveaux_noms = list(form.cleaned_data.get("fournisseurs_nouveaux") or [])

    resultat: list[Fournisseur] = []
    ids_vus: set[int] = set()
    noms_crees: list[str] = []

    for fournisseur in fournisseurs_selectionnes:
        if fournisseur.pk not in ids_vus:
            resultat.append(fournisseur)
            ids_vus.add(fournisseur.pk)

    for nom in fournisseurs_nouveaux_noms:
        fournisseur, cree = _get_or_create_fournisseur(nom)
        if fournisseur.pk not in ids_vus:
            resultat.append(fournisseur)
            ids_vus.add(fournisseur.pk)
        if cree:
            noms_crees.append(fournisseur.nom)

    return resultat, noms_crees


def _synchroniser_fournisseurs_article(
    article: Article,
    fournisseurs: Iterable[Fournisseur],
) -> None:
    fournisseurs = list(fournisseurs)
    fournisseur_ids = [f.pk for f in fournisseurs]

    ArticleFournisseur.objects.filter(article=article).exclude(
        fournisseur_id__in=fournisseur_ids
    ).delete()

    for fournisseur in fournisseurs:
        ArticleFournisseur.objects.get_or_create(
            article=article,
            fournisseur=fournisseur,
        )


def _unites_personnalisees_disponibles(*, unite_courante: str = "") -> list[str]:
    unite_courante = _normaliser_libelle_unite(unite_courante or "")
    valeurs = set()

    for unite in Article.objects.exclude(unite__isnull=True).exclude(unite__exact="").values_list("unite", flat=True):
        normalisee = _normaliser_libelle_unite(unite or "")
        if not normalisee:
            continue
        if normalisee in UNITES_STANDARD:
            continue
        valeurs.add(normalisee)

    if unite_courante and unite_courante not in UNITES_STANDARD:
        valeurs.add(unite_courante)

    return sorted(valeurs, key=lambda x: x.casefold())


def _article_peut_etre_supprime(article: Article) -> bool:
    if not article.pk:
        return True
    return not (article.a_historique_mouvements() or article.a_historique_requisitions())


@login_required
@articles_required
def liste_articles(request):
    q = (request.GET.get("q") or "").strip()
    cat = (request.GET.get("cat") or "").strip()

    qs = (
        Article.objects.select_related("categorie", "utilisateur_enregistreur")
        .all()
        .order_by("nom")
    )

    if q:
        qs = qs.filter(
            Q(nom__icontains=q)
            | Q(unite__icontains=q)
            | Q(unite_base__icontains=q)
            | Q(categorie__libelle__icontains=q)
        )

    if cat.isdigit():
        qs = qs.filter(categorie_id=int(cat))

    paginator = Paginator(qs, ARTICLES_PAR_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    for article in page_obj.object_list:
        article.peut_supprimer = _article_peut_etre_supprime(article)

    categories = Categorie.objects.all().order_by("libelle")

    return render(
        request,
        "articles/liste.html",
        {
            "articles": page_obj,
            "page_obj": page_obj,
            "q": q,
            "categories": categories,
            "cat": cat,
        },
    )


@login_required
@articles_required
@transaction.atomic
def creer_article(request):
    if request.method == "POST":
        form = ArticleForm(request.POST)
        if form.is_valid():
            categorie_choisie = form.cleaned_data.get("categorie")
            categorie_libre = _normaliser_texte(form.cleaned_data.get("categorie_libre"))

            categorie = categorie_choisie
            categorie_creee = False

            if categorie_libre:
                categorie, categorie_creee = _get_or_create_categorie(categorie_libre)

            fournisseurs, fournisseurs_crees = _collecter_fournisseurs_depuis_form(form)

            article = form.save(commit=False)
            article.categorie = categorie
            article.utilisateur_enregistreur = request.user
            article.full_clean()
            article.save()

            _synchroniser_fournisseurs_article(article, fournisseurs)

            enregistrer_audit(
                action=AuditLog.Action.CREATION,
                user=request.user,
                request=request,
                app_label="articles",
                cible=article,
                message="Création d'un article.",
                meta={
                    "nom": article.nom,
                    "conditionnement_principal": article.unite,
                    "unite_base": article.unite_base,
                    "quantite_par_conditionnement": article.quantite_par_conditionnement,
                    "resume_conditionnement": article.resume_conditionnement,
                    "categorie": str(article.categorie),
                    "categorie_creee": categorie_creee,
                    "stock_initial_unites": article.stock_initial,
                    "stock_initial_affichage": article.stock_initial_affichage,
                    "stock_actuel_unites": article.stock_actuel,
                    "stock_actuel_affichage": article.stock_actuel_affichage,
                    "stock_minimal_unites": article.stock_minimal,
                    "stock_minimal_affichage": article.stock_minimal_affichage,
                    "fournisseurs": [f.nom for f in fournisseurs],
                    "fournisseurs_crees": fournisseurs_crees,
                },
            )

            messages.success(
                request,
                (
                    "Article enregistré avec succès. "
                    f"Stock actuel : {article.stock_actuel_affichage}."
                ),
            )
            return redirect("articles:liste")

        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
        unite_courante = request.POST.get("unite", "")
    else:
        form = ArticleForm()
        unite_courante = ""

    return render(
        request,
        "articles/form_article.html",
        {
            "form": form,
            "mode": "create",
            "unites_personnalisees": _unites_personnalisees_disponibles(
                unite_courante=unite_courante
            ),
        },
    )


@login_required
@articles_required
@transaction.atomic
def modifier_article(request, pk: int):
    article = get_object_or_404(Article, pk=pk)

    if request.method == "POST":
        form = ArticleForm(request.POST, instance=article)
        if form.is_valid():
            ancien = {
                "nom": article.nom,
                "unite": article.unite,
                "unite_base": article.unite_base,
                "quantite_par_conditionnement": article.quantite_par_conditionnement,
                "categorie": str(article.categorie),
                "stock_initial": article.stock_initial,
                "stock_initial_affichage": article.stock_initial_affichage,
                "stock_actuel": article.stock_actuel,
                "stock_actuel_affichage": article.stock_actuel_affichage,
                "stock_minimal": article.stock_minimal,
                "stock_minimal_affichage": article.stock_minimal_affichage,
                "fournisseurs": list(
                    article.fournisseurs.all().order_by("nom").values_list("nom", flat=True)
                ),
            }

            categorie_choisie = form.cleaned_data.get("categorie")
            categorie_libre = _normaliser_texte(form.cleaned_data.get("categorie_libre"))

            categorie = categorie_choisie
            categorie_creee = False

            if categorie_libre:
                categorie, categorie_creee = _get_or_create_categorie(categorie_libre)

            fournisseurs, fournisseurs_crees = _collecter_fournisseurs_depuis_form(form)

            obj = form.save(commit=False)
            obj.categorie = categorie
            obj.full_clean()
            obj.save()

            _synchroniser_fournisseurs_article(obj, fournisseurs)

            enregistrer_audit(
                action=AuditLog.Action.MODIFICATION,
                user=request.user,
                request=request,
                app_label="articles",
                cible=obj,
                message="Modification d'un article.",
                meta={
                    "avant": ancien,
                    "apres": {
                        "nom": obj.nom,
                        "unite": obj.unite,
                        "unite_base": obj.unite_base,
                        "quantite_par_conditionnement": obj.quantite_par_conditionnement,
                        "resume_conditionnement": obj.resume_conditionnement,
                        "categorie": str(obj.categorie),
                        "categorie_creee": categorie_creee,
                        "stock_initial": obj.stock_initial,
                        "stock_initial_affichage": obj.stock_initial_affichage,
                        "stock_actuel": obj.stock_actuel,
                        "stock_actuel_affichage": obj.stock_actuel_affichage,
                        "stock_minimal": obj.stock_minimal,
                        "stock_minimal_affichage": obj.stock_minimal_affichage,
                        "fournisseurs": [f.nom for f in fournisseurs],
                        "fournisseurs_crees": fournisseurs_crees,
                    },
                },
            )

            messages.success(request, "Article mis à jour.")
            return redirect("articles:liste")

        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
        unite_courante = request.POST.get("unite", article.unite)
    else:
        form = ArticleForm(instance=article)
        unite_courante = article.unite

    return render(
        request,
        "articles/form_article.html",
        {
            "form": form,
            "mode": "edit",
            "article": article,
            "unites_personnalisees": _unites_personnalisees_disponibles(
                unite_courante=unite_courante
            ),
        },
    )


@login_required
@articles_required
def supprimer_article(request, pk: int):
    article = get_object_or_404(Article, pk=pk)
    peut_supprimer = _article_peut_etre_supprime(article)

    if request.method == "POST":
        article_nom = article.nom
        article_unite = article.unite
        article_categorie = str(article.categorie)
        article_id = article.pk

        if not peut_supprimer:
            enregistrer_audit(
                action=AuditLog.Action.SUPPRESSION,
                user=request.user,
                request=request,
                app_label="articles",
                niveau=AuditLog.Niveau.WARNING,
                succes=False,
                cible_type="Article",
                cible_id=str(article_id),
                cible_label=f"{article_nom} ({article_unite})",
                message="Échec de suppression d'un article : article déjà lié à des mouvements ou réquisitions.",
                meta={
                    "nom": article_nom,
                    "unite": article_unite,
                    "categorie": article_categorie,
                    "stock_actuel": article.stock_actuel,
                    "stock_actuel_affichage": article.stock_actuel_affichage,
                    "motif": "article_lie_a_des_enregistrements_proteges",
                },
            )

            messages.error(
                request,
                (
                    f"Suppression impossible : l’article « {article_nom} » "
                    "a déjà des mouvements de stock ou des réquisitions liés."
                ),
            )
            return redirect("articles:liste")

        try:
            enregistrer_audit(
                action=AuditLog.Action.SUPPRESSION,
                user=request.user,
                request=request,
                app_label="articles",
                cible_type="Article",
                cible_id=str(article_id),
                cible_label=f"{article_nom} ({article_unite})",
                message="Suppression d'un article.",
                meta={
                    "nom": article_nom,
                    "unite": article_unite,
                    "categorie": article_categorie,
                    "stock_actuel": article.stock_actuel,
                    "stock_actuel_affichage": article.stock_actuel_affichage,
                },
            )

            article.delete()
            messages.success(request, "Article supprimé.")
            return redirect("articles:liste")

        except ProtectedError:
            enregistrer_audit(
                action=AuditLog.Action.SUPPRESSION,
                user=request.user,
                request=request,
                app_label="articles",
                niveau=AuditLog.Niveau.WARNING,
                succes=False,
                cible_type="Article",
                cible_id=str(article_id),
                cible_label=f"{article_nom} ({article_unite})",
                message="Échec de suppression d'un article : article déjà lié à d'autres enregistrements.",
                meta={
                    "nom": article_nom,
                    "unite": article_unite,
                    "categorie": article_categorie,
                    "stock_actuel": article.stock_actuel,
                    "stock_actuel_affichage": article.stock_actuel_affichage,
                    "motif": "article_lie_a_des_enregistrements_proteges",
                },
            )

            messages.error(
                request,
                (
                    f"Suppression impossible : l’article « {article_nom} » "
                    "est déjà utilisé dans des mouvements de stock, réquisitions "
                    "ou d'autres enregistrements liés."
                ),
            )
            return redirect("articles:liste")

    return render(
        request,
        "articles/confirm_delete.html",
        {
            "article": article,
            "peut_supprimer": peut_supprimer,
        },
    )


@login_required
@articles_required
def liste_categories(request):
    q = (request.GET.get("q") or "").strip()
    qs = Categorie.objects.annotate(nombre_articles=Count("articles")).order_by("libelle")

    if q:
        qs = qs.filter(libelle__icontains=q)

    for categorie in qs:
        categorie.peut_supprimer = categorie.nombre_articles == 0

    return render(request, "articles/categories.html", {"categories": qs, "q": q})


@login_required
@articles_required
def creer_categorie(request):
    if request.method == "POST":
        form = CategorieForm(request.POST)
        if form.is_valid():
            categorie = form.save()

            enregistrer_audit(
                action=AuditLog.Action.CREATION,
                user=request.user,
                request=request,
                app_label="articles",
                cible_type="Categorie",
                cible_id=str(categorie.pk),
                cible_label=str(categorie),
                message="Création d'une catégorie d'article.",
                meta={
                    "libelle": categorie.libelle,
                },
            )

            messages.success(request, "Catégorie créée.")
            return redirect("articles:categories")

        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = CategorieForm()

    return render(
        request,
        "articles/form_categorie.html",
        {"form": form, "mode": "create"},
    )


@login_required
@articles_required
def modifier_categorie(request, pk: int):
    categorie = get_object_or_404(Categorie, pk=pk)

    if request.method == "POST":
        form = CategorieForm(request.POST, instance=categorie)
        if form.is_valid():
            ancien_libelle = categorie.libelle
            categorie = form.save()

            enregistrer_audit(
                action=AuditLog.Action.MODIFICATION,
                user=request.user,
                request=request,
                app_label="articles",
                cible_type="Categorie",
                cible_id=str(categorie.pk),
                cible_label=str(categorie),
                message="Modification d'une catégorie d'article.",
                meta={
                    "avant": {"libelle": ancien_libelle},
                    "apres": {"libelle": categorie.libelle},
                },
            )

            messages.success(request, "Catégorie mise à jour.")
            return redirect("articles:categories")

        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = CategorieForm(instance=categorie)

    return render(
        request,
        "articles/form_categorie.html",
        {
            "form": form,
            "mode": "edit",
            "categorie": categorie,
        },
    )


@login_required
@articles_required
def supprimer_categorie(request, pk: int):
    categorie = get_object_or_404(
        Categorie.objects.annotate(nombre_articles=Count("articles")),
        pk=pk,
    )
    peut_supprimer = categorie.nombre_articles == 0

    if request.method == "POST":
        if not peut_supprimer:
            enregistrer_audit(
                action=AuditLog.Action.SUPPRESSION,
                user=request.user,
                request=request,
                app_label="articles",
                niveau=AuditLog.Niveau.WARNING,
                succes=False,
                cible_type="Categorie",
                cible_id=str(categorie.pk),
                cible_label=str(categorie),
                message="Échec de suppression d'une catégorie d'article : catégorie liée à des articles.",
                meta={
                    "libelle": categorie.libelle,
                    "motif": "categorie_contient_des_articles",
                    "nombre_articles": categorie.nombre_articles,
                },
            )

            messages.error(
                request,
                "Suppression impossible : cette catégorie contient déjà des articles.",
            )
            return redirect("articles:categories")

        categorie_id = categorie.pk
        categorie_libelle = categorie.libelle

        enregistrer_audit(
            action=AuditLog.Action.SUPPRESSION,
            user=request.user,
            request=request,
            app_label="articles",
            cible_type="Categorie",
            cible_id=str(categorie_id),
            cible_label=categorie_libelle,
            message="Suppression d'une catégorie d'article.",
            meta={
                "libelle": categorie_libelle,
            },
        )

        categorie.delete()
        messages.success(request, "Catégorie supprimée.")
        return redirect("articles:categories")

    return render(
        request,
        "articles/confirm_delete_categorie.html",
        {
            "categorie": categorie,
            "peut_supprimer": peut_supprimer,
        },
    )


@login_required
@articles_required
def detail_article(request, pk: int):
    article = get_object_or_404(
        Article.objects.select_related("categorie", "utilisateur_enregistreur"),
        pk=pk,
    )

    liens_qs = article.liens_fournisseurs.select_related("fournisseur").all()
    has_fournisseurs = liens_qs.exists()
    peut_supprimer = _article_peut_etre_supprime(article)

    enregistrer_audit(
        action=AuditLog.Action.CONSULTATION,
        user=request.user,
        request=request,
        app_label="articles",
        cible=article,
        message="Consultation du détail d'un article.",
        meta={
            "nom": article.nom,
            "categorie": str(article.categorie),
            "conditionnement_principal": article.unite,
            "quantite_par_conditionnement": article.quantite_par_conditionnement,
            "stock_actuel": article.stock_actuel,
            "stock_actuel_affichage": article.stock_actuel_affichage,
            "has_fournisseurs": has_fournisseurs,
            "nombre_fournisseurs": liens_qs.count(),
            "peut_supprimer": peut_supprimer,
        },
    )

    return render(
        request,
        "articles/detail.html",
        {
            "article": article,
            "liens_fournisseurs": liens_qs,
            "has_fournisseurs": has_fournisseurs,
            "peut_supprimer": peut_supprimer,
        },
    )