from datetime import date

from django.db import migrations


def _annee_fiscale_du_jour():
    today = date.today()
    if today.month >= 10:
        return today.year, today.year + 1
    return today.year - 1, today.year


def forward(apps, schema_editor):
    ConfigurationSysteme = apps.get_model("configurations", "ConfigurationSysteme")

    qs = ConfigurationSysteme.objects.all().order_by("-annee_debut", "-id")

    # Supprimer les lignes invalides si elles existent
    ConfigurationSysteme.objects.filter(annee_debut__isnull=True).delete()
    ConfigurationSysteme.objects.filter(annee_fin__isnull=True).delete()

    rows = list(ConfigurationSysteme.objects.all().order_by("-annee_debut", "-id"))

    if not rows:
        debut, fin = _annee_fiscale_du_jour()
        ConfigurationSysteme.objects.create(
            annee_debut=debut,
            annee_fin=fin,
            est_active=True,
        )
        return

    # Tout désactiver
    ConfigurationSysteme.objects.all().update(est_active=False)

    # Garder la plus récente active
    plus_recente = rows[0]
    plus_recente.est_active = True
    plus_recente.save(update_fields=["est_active"])


def backward(apps, schema_editor):
    ConfigurationSysteme = apps.get_model("configurations", "ConfigurationSysteme")
    ConfigurationSysteme.objects.all().update(est_active=False)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("configurations", "0003_add_est_active"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]