from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("requisitions", "0002_initial"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="requisition",
            name="requisition_directi_ba8796_idx",
        ),
        migrations.RemoveField(
            model_name="requisition",
            name="direction_demandeuse",
        ),
    ]