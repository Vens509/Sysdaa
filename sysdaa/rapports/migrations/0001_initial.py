from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
from django.utils import timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Rapport",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("type_rapport", models.CharField(choices=[("STOCK_MENSUEL", "Stock mensuel")], max_length=50)),
                ("format_rapport", models.CharField(choices=[("PDF", "PDF"), ("EXCEL", "Excel (CSV)")], max_length=10)),
                ("date_generation", models.DateTimeField(default=timezone.now)),
                ("url_fichier", models.TextField(blank=True)),
                ("fichier", models.FileField(blank=True, null=True, upload_to="rapports/%Y/%m/")),
                ("mois", models.PositiveSmallIntegerField()),
                ("annee", models.PositiveSmallIntegerField()),
                ("consultant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="rapports_generes", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Rapport",
                "verbose_name_plural": "Rapports",
                "ordering": ("-date_generation", "-id"),
            },
        ),
        migrations.AddIndex(
            model_name="rapport",
            index=models.Index(fields=["type_rapport"], name="rapports_rap_type_ra_8f0e51_idx"),
        ),
        migrations.AddIndex(
            model_name="rapport",
            index=models.Index(fields=["date_generation"], name="rapports_rap_date_ge_7b1d08_idx"),
        ),
        migrations.AddIndex(
            model_name="rapport",
            index=models.Index(fields=["annee", "mois"], name="rapports_rap_annee_m_2d5c1a_idx"),
        ),
    ]
