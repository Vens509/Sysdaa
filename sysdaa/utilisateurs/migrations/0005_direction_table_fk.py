from __future__ import annotations

from django.db import migrations, models


def forwards(apps, schema_editor):
    Utilisateur = apps.get_model("utilisateurs", "Utilisateur")
    Direction = apps.get_model("utilisateurs", "Direction")

    # 1) Créer les Directions depuis l'ancien champ texte
    noms = (
        Utilisateur.objects
        .exclude(direction_affectee__isnull=True)
        .exclude(direction_affectee__exact="")
        .values_list("direction_affectee", flat=True)
        .distinct()
    )

    # mapping nom -> id
    by_name = {}
    for nom in noms:
        nom_clean = (nom or "").strip()
        if not nom_clean:
            continue
        obj, _ = Direction.objects.get_or_create(nom=nom_clean)
        by_name[nom_clean] = obj.id

    # 2) Remplir le nouveau FK
    # direction_affectee_fk est ajouté juste après (dans operations)
    for u in Utilisateur.objects.all().only("id", "direction_affectee"):
        nom_clean = (u.direction_affectee or "").strip()
        if not nom_clean:
            continue
        did = by_name.get(nom_clean)
        if did:
            Utilisateur.objects.filter(pk=u.pk).update(direction_affectee_fk_id=did)


def backwards(apps, schema_editor):
    # Retour arrière : on ne reconstruit pas automatiquement le texte (on laisse vide).
    # (Le downgrade reste possible mais sans réécrire direction_affectee texte.)
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("utilisateurs", "0004_utilisateur_direction_affectee"),
    ]

    operations = [
        # A) Créer la table Direction
        migrations.CreateModel(
            name="Direction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nom", models.CharField(max_length=150, unique=True)),
            ],
            options={
                "verbose_name": "Direction",
                "verbose_name_plural": "Directions",
                "ordering": ("nom",),
            },
        ),

        # B) Ajouter un FK temporaire (on ne casse rien)
        migrations.AddField(
            model_name="utilisateur",
            name="direction_affectee_fk",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.PROTECT,
                related_name="utilisateurs",
                to="utilisateurs.direction",
                verbose_name="Direction affectée",
            ),
        ),

        # C) Data migration (copie du texte -> Direction + FK)
        migrations.RunPython(forwards, backwards),

        # D) Supprimer l'ancien champ texte
        migrations.RemoveField(
            model_name="utilisateur",
            name="direction_affectee",
        ),

        # E) Renommer le FK temporaire en direction_affectee (nom final attendu dans le code)
        migrations.RenameField(
            model_name="utilisateur",
            old_name="direction_affectee_fk",
            new_name="direction_affectee",
        ),
    ]