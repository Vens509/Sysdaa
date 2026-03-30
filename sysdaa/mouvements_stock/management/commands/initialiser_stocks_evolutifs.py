import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from articles.models import Article
from mouvements_stock.services import enregistrer_entree_stock
from utilisateurs.models import Utilisateur
from core.permissions import ROLE_GESTIONNAIRE

class Command(BaseCommand):
    help = "Simule des entrées de stock réparties sur Janvier, Février et Mars 2026."

    def handle(self, *args, **options):
        gestionnaire = Utilisateur.objects.filter(role__nom_role=ROLE_GESTIONNAIRE).first()
        if not gestionnaire:
            self.stdout.write(self.style.ERROR("Aucun gestionnaire trouvé."))
            return

        articles = Article.objects.all()
        
        with transaction.atomic():
            for article in articles:
                # --- 1. DOTATION INITIALE (01 Janvier) ---
                stock_min = random.randint(10, 30)
                article.stock_minimal = stock_min
                article.save()

                # On commence avec 2x le stock minimal
                self._entree(article, stock_min * 2, datetime(2026, 1, 1, 9, 0), gestionnaire)

                # --- 2. RÉAPPROVISIONNEMENT (Février ou Mars) ---
                # On simule une livraison fournisseur aléatoire pour montrer du mouvement
                mois_livraison = random.choice([2, 3]) 
                jour_livraison = random.randint(1, 15)
                date_livraison = datetime(2026, mois_livraison, jour_livraison, 10, 0)
                
                # Livraison de secours (entre 50 et 100 unités)
                quantite_sup = random.randint(50, 150)
                self._entree(article, quantite_sup, date_livraison, gestionnaire)

        self.stdout.write(self.style.SUCCESS("Entrées étalées sur 3 mois générées avec succès !"))

    def _entree(self, article, qte, date_dt, acteur):
        date_aware = timezone.make_aware(date_dt)
        enregistrer_entree_stock(
            article=article,
            quantite=qte,
            conditionnement_mouvement=article.unite or "Unité",
            quantite_par_conditionnement_mouvement=1,
            date_mouvement=date_aware,
            acteur=acteur
        )