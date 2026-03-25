from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("configurations", "0006_alter_configurationsysteme_options_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ClotureStockMensuelle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("annee", models.IntegerField()),
                ("mois", models.PositiveSmallIntegerField()),
                ("date_execution", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("nombre_articles_total", models.PositiveIntegerField(default=0)),
                ("nombre_articles_mis_a_jour", models.PositiveIntegerField(default=0)),
                (
                    "configurateur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="clotures_stock_mensuelles_creees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Clôture stock mensuelle",
                "verbose_name_plural": "Clôtures stock mensuelles",
                "db_table": "clotures_stock_mensuelles",
                "ordering": ["-annee", "-mois", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="cloturestockmensuelle",
            index=models.Index(fields=["annee", "mois"], name="clotures_st_annee_8f676f_idx"),
        ),
        migrations.AddIndex(
            model_name="cloturestockmensuelle",
            index=models.Index(fields=["date_execution"], name="clotures_st_date_ex_55411d_idx"),
        ),
        migrations.AddConstraint(
            model_name="cloturestockmensuelle",
            constraint=models.UniqueConstraint(
                fields=("annee", "mois"),
                name="uq_cloture_stock_mensuelle_periode",
            ),
        ),
        migrations.AddConstraint(
            model_name="cloturestockmensuelle",
            constraint=models.CheckConstraint(
                condition=models.Q(("mois__gte", 1), ("mois__lte", 12)),
                name="ck_cloture_stock_mensuelle_mois_1_12",
            ),
        ),
    ]
