from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("utilisateurs", "0003_utilisateur_telephone"),
    ]

    operations = [
        migrations.AddField(
            model_name="utilisateur",
            name="direction_affectee",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
    ]