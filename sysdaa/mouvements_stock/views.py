from __future__ import annotations

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render

from audit.models import AuditLog
from audit.services import audit_log as enregistrer_audit

from requisitions.permissions import ROLE_DIRECTEUR_DAA, ROLE_GESTIONNAIRE, role_required

from articles.models import Article

from .forms import EntreeStockForm, SortieStockForm
from .models import MouvementStock
from .services import enregistrer_entree_stock, enregistrer_sortie_stock


@role_required(ROLE_GESTIONNAIRE, ROLE_DIRECTEUR_DAA)
def entree_stock(request):
    if request.method == "POST":
        form = EntreeStockForm(request.POST)
        if form.is_valid():
            article = form.cleaned_data["article"]
            quantite = form.cleaned_data["quantite"]
            conditionnement_mouvement = form.cleaned_data["conditionnement_mouvement"]
            qpc_mouvement = form.cleaned_data["quantite_par_conditionnement_mouvement"]
            quantite_unites = form.cleaned_data["quantite_unites"]

            try:
                stock_avant = int(article.stock_actuel or 0)

                result = enregistrer_entree_stock(
                    article=article,
                    quantite=quantite,
                    conditionnement_mouvement=conditionnement_mouvement,
                    quantite_par_conditionnement_mouvement=qpc_mouvement,
                    acteur=request.user,
                )

                enregistrer_audit(
                    action=AuditLog.Action.CREATION,
                    user=request.user,
                    request=request,
                    app_label="mouvements_stock",
                    cible_type="MouvementStock",
                    cible_id=str(result.mouvement_id),
                    cible_label=f"Entrée stock #{result.mouvement_id}",
                    message="Enregistrement d'une entrée de stock.",
                    meta={
                        "type_mouvement": MouvementStock.TypeMouvement.ENTREE,
                        "mouvement_id": result.mouvement_id,
                        "article_id": article.pk,
                        "article_nom": article.nom,
                        "quantite": quantite,
                        "conditionnement_mouvement": conditionnement_mouvement,
                        "quantite_par_conditionnement_mouvement": qpc_mouvement,
                        "quantite_unites": quantite_unites,
                        "stock_avant": stock_avant,
                        "stock_apres": result.nouveau_stock,
                    },
                )

                messages.success(
                    request,
                    (
                        f"Entrée enregistrée avec succès. "
                        f"Ajout réel : {quantite_unites} unité(s). "
                        f"Nouveau stock : {article.formater_quantite_pour_affichage(result.nouveau_stock)}"
                    ),
                )
                return redirect("mouvements_stock:liste_mouvements")

            except Exception as ex:
                enregistrer_audit(
                    action=AuditLog.Action.CREATION,
                    user=request.user,
                    request=request,
                    app_label="mouvements_stock",
                    niveau=AuditLog.Niveau.ERROR,
                    succes=False,
                    cible_type="Article",
                    cible_id=str(getattr(article, "pk", "") or ""),
                    cible_label=str(article),
                    message="Échec lors de l'enregistrement d'une entrée de stock.",
                    meta={
                        "type_mouvement": MouvementStock.TypeMouvement.ENTREE,
                        "article_id": getattr(article, "pk", None),
                        "article_nom": getattr(article, "nom", ""),
                        "quantite": quantite,
                        "conditionnement_mouvement": conditionnement_mouvement,
                        "quantite_par_conditionnement_mouvement": qpc_mouvement,
                        "quantite_unites": quantite_unites,
                        "erreur": str(ex),
                    },
                )
                messages.error(request, str(ex))
    else:
        form = EntreeStockForm()

    return render(
        request,
        "mouvements_stock/entree_stock.html",
        {"form": form},
    )


@role_required(ROLE_GESTIONNAIRE, ROLE_DIRECTEUR_DAA)
def sortie_stock(request):
    if request.method == "POST":
        form = SortieStockForm(request.POST)
        if form.is_valid():
            article = form.cleaned_data["article"]
            quantite = form.cleaned_data["quantite"]
            motif_sortie = form.cleaned_data["motif_sortie"]
            conditionnement_mouvement = form.cleaned_data["conditionnement_mouvement"]
            qpc_mouvement = form.cleaned_data["quantite_par_conditionnement_mouvement"]
            quantite_unites = form.cleaned_data["quantite_unites"]

            try:
                stock_avant = int(article.stock_actuel or 0)

                result = enregistrer_sortie_stock(
                    article=article,
                    quantite=quantite,
                    motif_sortie=motif_sortie,
                    conditionnement_mouvement=conditionnement_mouvement,
                    quantite_par_conditionnement_mouvement=qpc_mouvement,
                    acteur=request.user,
                )

                enregistrer_audit(
                    action=AuditLog.Action.CREATION,
                    user=request.user,
                    request=request,
                    app_label="mouvements_stock",
                    cible_type="MouvementStock",
                    cible_id=str(result.mouvement_id),
                    cible_label=f"Sortie stock #{result.mouvement_id}",
                    message="Enregistrement d'une sortie de stock hors réquisition.",
                    meta={
                        "type_mouvement": MouvementStock.TypeMouvement.SORTIE,
                        "mouvement_id": result.mouvement_id,
                        "article_id": article.pk,
                        "article_nom": article.nom,
                        "quantite": quantite,
                        "motif_sortie": motif_sortie,
                        "conditionnement_mouvement": conditionnement_mouvement,
                        "quantite_par_conditionnement_mouvement": qpc_mouvement,
                        "quantite_unites": quantite_unites,
                        "stock_avant": stock_avant,
                        "stock_apres": result.nouveau_stock,
                        "origine": "manuelle",
                    },
                )

                messages.success(
                    request,
                    (
                        f"Sortie enregistrée avec succès. "
                        f"Sortie réelle : {quantite_unites} unité(s). "
                        f"Nouveau stock : {article.formater_quantite_pour_affichage(result.nouveau_stock)}"
                    ),
                )
                return redirect("mouvements_stock:liste_mouvements")

            except Exception as ex:
                enregistrer_audit(
                    action=AuditLog.Action.CREATION,
                    user=request.user,
                    request=request,
                    app_label="mouvements_stock",
                    niveau=AuditLog.Niveau.ERROR,
                    succes=False,
                    cible_type="Article",
                    cible_id=str(getattr(article, "pk", "") or ""),
                    cible_label=str(article),
                    message="Échec lors de l'enregistrement d'une sortie de stock hors réquisition.",
                    meta={
                        "type_mouvement": MouvementStock.TypeMouvement.SORTIE,
                        "article_id": getattr(article, "pk", None),
                        "article_nom": getattr(article, "nom", ""),
                        "quantite": quantite,
                        "motif_sortie": motif_sortie,
                        "conditionnement_mouvement": conditionnement_mouvement,
                        "quantite_par_conditionnement_mouvement": qpc_mouvement,
                        "quantite_unites": quantite_unites,
                        "origine": "manuelle",
                        "erreur": str(ex),
                    },
                )
                messages.error(request, str(ex))
    else:
        form = SortieStockForm()

    return render(
        request,
        "mouvements_stock/sortie_stock.html",
        {"form": form},
    )


@role_required(ROLE_GESTIONNAIRE, ROLE_DIRECTEUR_DAA)
def liste_mouvements(request):
    q = (request.GET.get("q") or "").strip()
    type_mv = (request.GET.get("type") or "").strip()
    page_number = request.GET.get("page")

    qs = MouvementStock.objects.select_related(
        "article",
        "article__categorie",
        "requisition",
        "requisition__soumetteur",
        "requisition__soumetteur__direction_affectee",
    )

    if type_mv in (
        MouvementStock.TypeMouvement.ENTREE,
        MouvementStock.TypeMouvement.SORTIE,
    ):
        qs = qs.filter(type_mouvement=type_mv)

    if q:
        qs = qs.filter(
            Q(article__nom__icontains=q)
            | Q(article__categorie__libelle__icontains=q)
            | Q(motif_sortie__icontains=q)
            | Q(conditionnement_mouvement__icontains=q)
            | Q(requisition__motif_global__icontains=q)
            | Q(requisition__soumetteur__email__icontains=q)
            | Q(requisition__soumetteur__direction_affectee__nom__icontains=q)
        )

    qs = qs.order_by("-date_mouvement", "-id")
    total_resultats = qs.count()

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(page_number)
    mouvements = page_obj.object_list

    enregistrer_audit(
        action=AuditLog.Action.CONSULTATION,
        user=request.user,
        request=request,
        app_label="mouvements_stock",
        message="Consultation de la liste des mouvements de stock.",
        meta={
            "q": q,
            "type_mouvement": type_mv,
            "nombre_resultats": total_resultats,
            "page": page_obj.number,
        },
    )

    return render(
        request,
        "mouvements_stock/liste_mouvements.html",
        {
            "mouvements": mouvements,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "total_resultats": total_resultats,
            "q": q,
            "type": type_mv,
            "types": MouvementStock.TypeMouvement.choices,
        },
    )


@role_required(ROLE_GESTIONNAIRE, ROLE_DIRECTEUR_DAA)
def etat_stock(request):
    q = (request.GET.get("q") or "").strip()

    qs = Article.objects.select_related("categorie").order_by("nom", "id")

    if q:
        qs = qs.filter(
            Q(nom__icontains=q)
            | Q(categorie__libelle__icontains=q)
            | Q(unite__icontains=q)
        )

    articles = qs

    enregistrer_audit(
        action=AuditLog.Action.CONSULTATION,
        user=request.user,
        request=request,
        app_label="mouvements_stock",
        message="Consultation de l'état du stock.",
        meta={
            "q": q,
            "nombre_articles": articles.count(),
        },
    )

    return render(
        request,
        "mouvements_stock/etat_stock.html",
        {
            "articles": articles,
            "q": q,
        },
    )