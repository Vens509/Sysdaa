from __future__ import annotations

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


DIRECTEUR_DIRECTION_ROLE_NAME = "Directeur de direction"
ASSISTANT_DIRECTEUR_ROLE_NAME = "Assistant de directeur"


class Role(models.Model):
    nom_role = models.CharField(max_length=120, unique=True)

    class Meta:
        verbose_name = "Rôle"
        verbose_name_plural = "Rôles"

    def __str__(self) -> str:
        return self.nom_role


class Permission(models.Model):
    nom_permission = models.CharField(max_length=150, unique=True)

    class Meta:
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"

    def __str__(self) -> str:
        return self.nom_permission


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="permission_roles")

    class Meta:
        verbose_name = "Rôle-Permission"
        verbose_name_plural = "Rôles-Permissions"
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="uq_role_permission")
        ]

    def __str__(self) -> str:
        return f"{self.role} -> {self.permission}"


class Direction(models.Model):
    nom = models.CharField(max_length=150, unique=True)

    class Meta:
        verbose_name = "Direction"
        verbose_name_plural = "Directions"
        ordering = ("nom",)

    def __str__(self) -> str:
        return self.nom


class UtilisateurManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("L'email est obligatoire.")
        email = self.normalize_email(email)

        if extra_fields.get("role") is None:
            raise ValueError("Le rôle est obligatoire pour créer un utilisateur.")

        user = self.model(email=email, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.full_clean()
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("statut", Utilisateur.STATUT_ACTIF)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Un superuser doit avoir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Un superuser doit avoir is_superuser=True.")

        if extra_fields.get("role") is None:
            role_sa, _ = Role.objects.get_or_create(nom_role="Super Admin")
            extra_fields["role"] = role_sa

        return self.create_user(email=email, password=password, **extra_fields)


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    STATUT_ACTIF = "Actif"
    STATUT_INACTIF = "Inactif"
    STATUTS = (
        (STATUT_ACTIF, STATUT_ACTIF),
        (STATUT_INACTIF, STATUT_INACTIF),
    )

    nom = models.CharField(max_length=120)
    prenom = models.CharField(max_length=120)
    email = models.EmailField(unique=True)

    telephone = models.CharField(max_length=20, unique=True, null=True, blank=True)

    direction_affectee = models.ForeignKey(
        Direction,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="utilisateurs",
        verbose_name="Direction affectée",
    )

    directeur_superviseur = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assistants_directeurs",
        verbose_name="Directeur rattaché",
    )

    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="utilisateurs")
    statut = models.CharField(max_length=10, choices=STATUTS, default=STATUT_ACTIF)

    is_directeur_direction = models.BooleanField(default=False, editable=False)
    is_assistant_directeur = models.BooleanField(default=False, editable=False)

    date_creation = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UtilisateurManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nom", "prenom"]

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["nom"]),
            models.Index(fields=["prenom"]),
            models.Index(fields=["statut"]),
            models.Index(fields=["direction_affectee"]),
            models.Index(fields=["directeur_superviseur"]),
            models.Index(fields=["is_directeur_direction"]),
            models.Index(fields=["is_assistant_directeur"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["direction_affectee"],
                condition=Q(
                    is_directeur_direction=True,
                    statut="Actif",
                    direction_affectee__isnull=False,
                ),
                name="uq_one_active_directeur_direction_per_direction",
            ),
            models.UniqueConstraint(
                fields=["direction_affectee"],
                condition=Q(
                    is_assistant_directeur=True,
                    statut="Actif",
                    direction_affectee__isnull=False,
                ),
                name="uq_one_active_assistant_direction_per_direction",
            ),
            models.UniqueConstraint(
                fields=["directeur_superviseur"],
                condition=Q(
                    is_assistant_directeur=True,
                    statut="Actif",
                    directeur_superviseur__isnull=False,
                ),
                name="uq_one_active_assistant_per_directeur",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.prenom} {self.nom} ({self.email})"

    def _sync_active_status(self) -> None:
        if self.statut == self.STATUT_INACTIF:
            self.is_active = False
        elif self.statut == self.STATUT_ACTIF:
            self.is_active = True

    def _sync_role_flags(self) -> None:
        rn = ""
        try:
            if self.role_id:
                rn = (self.role.nom_role or "").strip()
        except Exception:
            rn = ""

        self.is_directeur_direction = rn == DIRECTEUR_DIRECTION_ROLE_NAME
        self.is_assistant_directeur = rn == ASSISTANT_DIRECTEUR_ROLE_NAME

    def clean(self):
        if self.statut not in dict(self.STATUTS):
            raise ValidationError({"statut": "Statut invalide. Choisir 'Actif' ou 'Inactif'."})

        self._sync_role_flags()
        self._sync_active_status()

        errors: dict[str, str] = {}

        if (self.is_directeur_direction or self.is_assistant_directeur) and not self.direction_affectee_id:
            errors["direction_affectee"] = "Une direction affectée est obligatoire pour ce rôle."

        if self.is_directeur_direction:
            self.directeur_superviseur = None

            if self.statut == self.STATUT_ACTIF and self.direction_affectee_id:
                qs = Utilisateur.objects.filter(
                    is_directeur_direction=True,
                    statut=self.STATUT_ACTIF,
                    direction_affectee_id=self.direction_affectee_id,
                )
                if self.pk:
                    qs = qs.exclude(pk=self.pk)
                if qs.exists():
                    errors["direction_affectee"] = (
                        "Cette direction a déjà un Directeur de direction actif."
                    )

        elif self.is_assistant_directeur:
            if not self.directeur_superviseur_id:
                errors["directeur_superviseur"] = (
                    "Veuillez sélectionner le Directeur de direction rattaché à cet assistant."
                )
            else:
                directeur = self.directeur_superviseur

                if self.pk and directeur.pk == self.pk:
                    errors["directeur_superviseur"] = "Un assistant ne peut pas être son propre directeur."
                elif not getattr(directeur, "is_directeur_direction", False):
                    errors["directeur_superviseur"] = (
                        "Le directeur rattaché doit avoir le rôle 'Directeur de direction'."
                    )
                else:
                    directeur_direction_id = getattr(directeur, "direction_affectee_id", None)
                    if self.direction_affectee_id and directeur_direction_id != self.direction_affectee_id:
                        errors["directeur_superviseur"] = (
                            "Le directeur rattaché doit appartenir à la même direction que l'assistant."
                        )
                    if getattr(directeur, "statut", None) != self.STATUT_ACTIF:
                        errors["directeur_superviseur"] = (
                            "Le directeur rattaché doit être actif."
                        )

            if self.statut == self.STATUT_ACTIF and self.direction_affectee_id:
                qs_direction = Utilisateur.objects.filter(
                    is_assistant_directeur=True,
                    statut=self.STATUT_ACTIF,
                    direction_affectee_id=self.direction_affectee_id,
                )
                if self.pk:
                    qs_direction = qs_direction.exclude(pk=self.pk)
                if qs_direction.exists():
                    errors["direction_affectee"] = (
                        "Cette direction a déjà un Assistant de directeur actif."
                    )

            if self.statut == self.STATUT_ACTIF and self.directeur_superviseur_id:
                qs_directeur = Utilisateur.objects.filter(
                    is_assistant_directeur=True,
                    statut=self.STATUT_ACTIF,
                    directeur_superviseur_id=self.directeur_superviseur_id,
                )
                if self.pk:
                    qs_directeur = qs_directeur.exclude(pk=self.pk)
                if qs_directeur.exists():
                    errors["directeur_superviseur"] = (
                        "Ce directeur a déjà un Assistant de directeur actif."
                    )
        else:
            self.directeur_superviseur = None

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self._sync_role_flags()
        self._sync_active_status()

        if not self.is_assistant_directeur:
            self.directeur_superviseur = None

        super().save(*args, **kwargs)