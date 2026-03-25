from __future__ import annotations

from django.db import models


class Fournisseur(models.Model):
    nom = models.CharField(max_length=150, unique=True)

    class Meta:
        db_table = "fournisseurs"
        ordering = ("nom",)
        verbose_name = "Fournisseur"
        verbose_name_plural = "Fournisseurs"

    def __str__(self) -> str:
        return self.nom


class AdresseFournisseur(models.Model):
    fournisseur = models.ForeignKey(Fournisseur, on_delete=models.CASCADE, related_name="adresses")
    numero = models.CharField(max_length=20, blank=True, default="")
    rue = models.CharField(max_length=150, blank=True, default="")
    ville = models.CharField(max_length=100, blank=True, default="")
    pays = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        db_table = "adresses_fournisseurs"
        ordering = ("pays", "ville", "rue", "numero")
        verbose_name = "Adresse fournisseur"
        verbose_name_plural = "Adresses fournisseurs"

    def __str__(self) -> str:
        parts = [self.numero, self.rue, self.ville, self.pays]
        return " ".join([p for p in parts if p]).strip() or f"Adresse ({self.fournisseur})"


class ArticleFournisseur(models.Model):
    article = models.ForeignKey("articles.Article", on_delete=models.CASCADE, related_name="liens_fournisseurs")
    fournisseur = models.ForeignKey(Fournisseur, on_delete=models.CASCADE, related_name="liens_articles")

    class Meta:
        db_table = "article_fournisseurs"
        verbose_name = "Article-Fournisseur"
        verbose_name_plural = "Articles-Fournisseurs"
        constraints = [
            models.UniqueConstraint(fields=["article", "fournisseur"], name="uq_article_fournisseur"),
        ]

    def __str__(self) -> str:
        return f"{self.article} -> {self.fournisseur}"