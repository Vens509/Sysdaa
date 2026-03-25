from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("requisitions", "0004_requisition_date_transfert_directeur_daa"),
    ]

    operations = [
        migrations.AddField(
            model_name="requisition",
            name="traitee_par",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="requisitions_traitees",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="requisition",
            name="recue_par",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="requisitions_recues",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]