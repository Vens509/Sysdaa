from django.contrib.auth import get_user_model
from django.test import TestCase
from django_otp.plugins.otp_email.models import EmailDevice

from .models import Role
from .services import synchroniser_email_otp_utilisateur

User = get_user_model()


class UtilisateurModelTests(TestCase):
    def test_create_user(self):
        role_utilisateur = Role.objects.create(nom_role="Secrétaire")

        u = User.objects.create_user(
            email="test@example.com",
            nom="Jean",
            prenom="Marc",
            role=role_utilisateur,
            password="StrongPass123!",
        )
        self.assertTrue(u.check_password("StrongPass123!"))
        self.assertEqual(u.email, "test@example.com")
        self.assertEqual(u.role, role_utilisateur)

    def test_create_superuser(self):
        su = User.objects.create_superuser(
            email="admin@example.com",
            nom="Admin",
            prenom="Root",
            password="StrongPass123!",
        )
        self.assertTrue(su.is_superuser)
        self.assertTrue(su.is_staff)

    def test_sync_email_otp_device(self):
        role_utilisateur = Role.objects.create(nom_role="Secrétaire")

        u = User.objects.create_user(
            email="otp@example.com",
            nom="Jean",
            prenom="OTP",
            role=role_utilisateur,
            password="StrongPass123!",
        )

        synchroniser_email_otp_utilisateur(u)

        self.assertTrue(
            EmailDevice.objects.filter(
                user=u,
                name="otp_email",
                email="otp@example.com",
            ).exists()
        )