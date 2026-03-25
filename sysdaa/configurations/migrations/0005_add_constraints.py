from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("configurations", "0004_normaliser_configurations_existantes"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="configurationsysteme",
            constraint=models.UniqueConstraint(
                fields=("annee_debut", "annee_fin"),
                name="uq_configuration_systeme_annee_fiscale",
            ),
        ),
        migrations.AddConstraint(
            model_name="configurationsysteme",
            constraint=models.UniqueConstraint(
                fields=("est_active",),
                condition=Q(est_active=True),
                name="uq_configuration_systeme_unique_active",
            ),
        ),
    ]