from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render

from articles.models import Article

from .forms import AdresseFournisseurForm, ArticleFournisseurForm, FournisseurForm
from .models import AdresseFournisseur, ArticleFournisseur, Fournisseur
from .permissions import fournisseurs_required


def _adresse_principale(fournisseur: Fournisseur) -> str:
    adresses = list(getattr(fournisseur, "adresses_prefetched", []))
    if not adresses:
        adresses = list(fournisseur.adresses.all())

    if not adresses:
        return "—"

    a = adresses[0]
    ligne_1 = " ".join([x for x in [a.numero, a.rue] if x]).strip()
    ligne_2 = ", ".join([x for x in [a.ville, a.pays] if x]).strip()

    texte = " — ".join([x for x in [ligne_1, ligne_2] if x]).strip()
    return texte or "—"


@login_required
@fournisseurs_required
def liste_fournisseurs(request):
    q = (request.GET.get("q") or "").strip()

    qs = (
        Fournisseur.objects
        .prefetch_related(
            Prefetch(
                "adresses",
                queryset=AdresseFournisseur.objects.order_by("pays", "ville", "rue", "numero"),
                to_attr="adresses_prefetched",
            ),
            Prefetch(
                "liens_articles",
                queryset=ArticleFournisseur.objects.select_related("article").order_by("article__nom"),
                to_attr="liens_articles_prefetched",
            ),
        )
        .all()
        .order_by("nom")
    )

    if q:
        qs = qs.filter(
            Q(nom__icontains=q)
            | Q(adresses__numero__icontains=q)
            | Q(adresses__rue__icontains=q)
            | Q(adresses__ville__icontains=q)
            | Q(adresses__pays__icontains=q)
        ).distinct()

    fournisseurs = []
    for fournisseur in qs:
        liaisons = list(getattr(fournisseur, "liens_articles_prefetched", []))
        fournisseur.adresse_principale = _adresse_principale(fournisseur)
        fournisseur.nb_articles = len(liaisons)
        fournisseurs.append(fournisseur)

    return render(
        request,
        "fournisseurs/liste.html",
        {
            "fournisseurs": fournisseurs,
            "q": q,
        },
    )


@login_required
@fournisseurs_required
def creer_fournisseur(request):
    if request.method == "POST":
        form = FournisseurForm(request.POST)
        if form.is_valid():
            fournisseur = form.save()
            messages.success(request, "Fournisseur créé.")
            return redirect("fournisseurs:detail", pk=fournisseur.pk)
        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = FournisseurForm()

    return render(
        request,
        "fournisseurs/form.html",
        {
            "form": form,
            "mode": "create",
        },
    )


@login_required
@fournisseurs_required
def modifier_fournisseur(request, pk: int):
    fournisseur = get_object_or_404(Fournisseur, pk=pk)

    if request.method == "POST":
        form = FournisseurForm(request.POST, instance=fournisseur)
        if form.is_valid():
            form.save()
            messages.success(request, "Fournisseur mis à jour.")
            return redirect("fournisseurs:detail", pk=fournisseur.pk)
        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = FournisseurForm(instance=fournisseur)

    return render(
        request,
        "fournisseurs/form.html",
        {
            "form": form,
            "mode": "edit",
            "fournisseur": fournisseur,
        },
    )


@login_required
@fournisseurs_required
def supprimer_fournisseur(request, pk: int):
    fournisseur = get_object_or_404(Fournisseur, pk=pk)

    if request.method == "POST":
        fournisseur.delete()
        messages.success(request, "Fournisseur supprimé.")
        return redirect("fournisseurs:liste")

    return render(
        request,
        "fournisseurs/confirm_delete.html",
        {
            "fournisseur": fournisseur,
        },
    )


@login_required
@fournisseurs_required
def detail_fournisseur(request, pk: int):
    fournisseur = get_object_or_404(
        Fournisseur.objects.prefetch_related(
            Prefetch(
                "adresses",
                queryset=AdresseFournisseur.objects.order_by("pays", "ville", "rue", "numero"),
            ),
            Prefetch(
                "liens_articles",
                queryset=ArticleFournisseur.objects.select_related("article", "article__categorie").order_by("article__nom"),
            ),
        ),
        pk=pk,
    )

    adresses = list(fournisseur.adresses.all())
    liaisons = list(fournisseur.liens_articles.all())

    return render(
        request,
        "fournisseurs/detail.html",
        {
            "fournisseur": fournisseur,
            "adresses": adresses,
            "liaisons": liaisons,
            "nb_adresses": len(adresses),
            "nb_articles": len(liaisons),
        },
    )


@login_required
@fournisseurs_required
def ajouter_adresse(request, fournisseur_pk: int):
    fournisseur = get_object_or_404(Fournisseur, pk=fournisseur_pk)

    if request.method == "POST":
        form = AdresseFournisseurForm(request.POST)
        if form.is_valid():
            adresse = form.save(commit=False)
            adresse.fournisseur = fournisseur
            adresse.save()
            messages.success(request, "Adresse ajoutée.")
            return redirect("fournisseurs:detail", pk=fournisseur.pk)
        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = AdresseFournisseurForm()

    return render(
        request,
        "fournisseurs/adresse_form.html",
        {
            "form": form,
            "fournisseur": fournisseur,
        },
    )


@login_required
@fournisseurs_required
def supprimer_adresse(request, fournisseur_pk: int, pk: int):
    fournisseur = get_object_or_404(Fournisseur, pk=fournisseur_pk)
    adresse = get_object_or_404(AdresseFournisseur, pk=pk, fournisseur=fournisseur)

    if request.method == "POST":
        adresse.delete()
        messages.success(request, "Adresse supprimée.")
        return redirect("fournisseurs:detail", pk=fournisseur.pk)

    return render(
        request,
        "fournisseurs/adresse_confirm_delete.html",
        {
            "fournisseur": fournisseur,
            "adresse": adresse,
        },
    )


@login_required
@fournisseurs_required
def lier_article(request, fournisseur_pk: int):
    fournisseur = get_object_or_404(Fournisseur, pk=fournisseur_pk)

    if request.method == "POST":
        form = ArticleFournisseurForm(request.POST)
        form.fields["article"].queryset = Article.objects.select_related("categorie").order_by("nom")

        if form.is_valid():
            article = form.cleaned_data["article"]

            existe = ArticleFournisseur.objects.filter(
                fournisseur=fournisseur,
                article=article,
            ).exists()

            if existe:
                messages.warning(request, "Cet article est déjà lié à ce fournisseur.")
                return redirect("fournisseurs:detail", pk=fournisseur.pk)

            ArticleFournisseur.objects.create(
                fournisseur=fournisseur,
                article=article,
            )
            messages.success(request, "Article lié au fournisseur.")
            return redirect("fournisseurs:detail", pk=fournisseur.pk)

        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = ArticleFournisseurForm()
        form.fields["article"].queryset = Article.objects.select_related("categorie").order_by("nom")

    return render(
        request,
        "fournisseurs/liaison_form.html",
        {
            "form": form,
            "fournisseur": fournisseur,
        },
    )


@login_required
@fournisseurs_required
def supprimer_liaison(request, fournisseur_pk: int, article_pk: int):
    fournisseur = get_object_or_404(Fournisseur, pk=fournisseur_pk)
    lien = get_object_or_404(
        ArticleFournisseur,
        fournisseur=fournisseur,
        article_id=article_pk,
    )

    if request.method == "POST":
        lien.delete()
        messages.success(request, "Liaison supprimée.")
        return redirect("fournisseurs:detail", pk=fournisseur.pk)

    return render(
        request,
        "fournisseurs/liaison_confirm_delete.html",
        {
            "fournisseur": fournisseur,
            "lien": lien,
        },
    )