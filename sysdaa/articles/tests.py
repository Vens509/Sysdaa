from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from utilisateurs.models import Role
from .models import Categorie, Article

User = get_user_model()


class ArticlesTests(TestCase):
    def setUp(self):
        self.role_gestionnaire = Role.objects.create(nom_role="Gestionnaire des ressources matérielles")
        self.role_secretaire = Role.objects.create(nom_role="Secrétaire")

        self.gestionnaire = User.objects.create_user(
            email="gest@example.com",
            nom="Gest",
            prenom="Ion",
            role=self.role_gestionnaire,
            password="Pass12345!",
        )
        self.secretaire = User.objects.create_user(
            email="sec@example.com",
            nom="Sec",
            prenom="Retaire",
            role=self.role_secretaire,
            password="Pass12345!",
        )
        self.cat = Categorie.objects.create(libelle="Fournitures")

    def test_creation_article_stock_actuel_equals_stock_initial(self):
        a = Article.objects.create(
            nom="Papier A4",
            unite="Paquet",
            stock_initial=10,
            stock_minimal=2,
            categorie=self.cat,
            utilisateur_enregistreur=self.gestionnaire,
        )
        self.assertEqual(a.stock_actuel, 10)

    def test_gestionnaire_can_access_create(self):
        self.client.login(email="gest@example.com", password="Pass12345!")
        r = self.client.get(reverse("articles:creer"))
        self.assertEqual(r.status_code, 200)

    def test_non_gestionnaire_forbidden_create(self):
        self.client.login(email="sec@example.com", password="Pass12345!")
        r = self.client.get(reverse("articles:creer"))
        self.assertEqual(r.status_code, 403)
