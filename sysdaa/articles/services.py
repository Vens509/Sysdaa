from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction

from .models import Article, Categorie, _normaliser_libelle_unite


@dataclass(frozen=True)
class CreationArticleResult:
    article_id: int


@transaction.atomic
def creer_article(
    *,
    nom: str,
    unite: str,
    quantite_par_conditionnement: int,
    stock_initial_conditionnements: int,
    stock_minimal_conditionnements: int,
    categorie: Categorie,
    utilisateur: Any,
) -> CreationArticleResult:
    unite = _normaliser_libelle_unite(unite)

    if unite == "Unité":
        quantite_par_conditionnement = 1
    elif unite == "Douzaine":
        quantite_par_conditionnement = 12

    stock_initial_unites = int(stock_initial_conditionnements) * int(quantite_par_conditionnement)
    stock_minimal_unites = int(stock_minimal_conditionnements) * int(quantite_par_conditionnement)

    article = Article(
        nom=nom,
        unite=unite,
        unite_base="Unité",
        quantite_par_conditionnement=quantite_par_conditionnement,
        stock_initial=stock_initial_unites,
        stock_actuel=stock_initial_unites,
        stock_minimal=stock_minimal_unites,
        categorie=categorie,
        utilisateur_enregistreur=utilisateur,
    )
    article.full_clean()
    article.save()

    return CreationArticleResult(article_id=article.id)
