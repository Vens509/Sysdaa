from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


ASSISTANT_ROLE_NAME = "Assistant de directeur"
DIRECTEUR_ROLE_NAME = "Directeur de direction"
STATUT_ACTIF = "Actif"


def create_role_and_sync_flags(apps, schema_editor):
    Role = apps.get_model("utilisateurs", "Role")
    Utilisateur = apps.get_model("utilisateurs", "Utilisateur")

    Role.objects.get_or_create(nom_role=ASSISTANT_ROLE_NAME)

    Utilisateur.objects.filter(role__nom_role=DIRECTEUR_ROLE_NAME).update(is_directeur_direction=True)
    Utilisateur.objects.exclude(role__nom_role=DIRECTEUR_ROLE_NAME).update(is_directeur_direction=False)
    Utilisateur.objects.filter(role__nom_role=ASSISTANT_ROLE_NAME).update(is_assistant_directeur=True)
    Utilisateur.objects.exclude(role__nom_role=ASSISTANT_ROLE_NAME).update(is_assistant_directeur=False)

    Utilisateur.objects.exclude(role__nom_role=ASSISTANT_ROLE_NAME).update(directeur_superviseur=None)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("utilisateurs", "0007_utilisateur_is_directeur_direction_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="utilisateur",
            name="directeur_superviseur",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assistants_directeurs",
                to="utilisateurs.utilisateur",
                verbose_name="Directeur rattaché",
            ),
        ),
        migrations.AddField(
            model_name="utilisateur",
            name="is_assistant_directeur",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddIndex(
            model_name="utilisateur",
            index=models.Index(fields=["directeur_superviseur"], name="utilisateur_directeu_4a5d9b_idx"),
        ),
        migrations.AddIndex(
            model_name="utilisateur",
            index=models.Index(fields=["is_assistant_directeur"], name="utilisateur_is_assis_6d439d_idx"),
        ),
        migrations.RunPython(create_role_and_sync_flags, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="utilisateur",
            name="uq_one_directeur_direction_per_direction",
        ),
        migrations.AddConstraint(
            model_name="utilisateur",
            constraint=models.UniqueConstraint(
                fields=("direction_affectee",),
                condition=Q(
                    is_directeur_direction=True,
                    statut=STATUT_ACTIF,
                    direction_affectee__isnull=False,
                ),
                name="uq_one_active_directeur_direction_per_direction",
            ),
        ),
        migrations.AddConstraint(
            model_name="utilisateur",
            constraint=models.UniqueConstraint(
                fields=("direction_affectee",),
                condition=Q(
                    is_assistant_directeur=True,
                    statut=STATUT_ACTIF,
                    direction_affectee__isnull=False,
                ),
                name="uq_one_active_assistant_direction_per_direction",
            ),
        ),
        migrations.AddConstraint(
            model_name="utilisateur",
            constraint=models.UniqueConstraint(
                fields=("directeur_superviseur",),
                condition=Q(
                    is_assistant_directeur=True,
                    statut=STATUT_ACTIF,
                    directeur_superviseur__isnull=False,
                ),
                name="uq_one_active_assistant_per_directeur",
            ),
        ),
    ]