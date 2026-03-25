# Generated manually for SYSDAA

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mouvements_stock", "0003_mouvementstock_motif_sortie_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="mouvementstock",
            name="conditionnement_mouvement",
            field=models.CharField(
                blank=True,
                default="Unité",
                help_text="Conditionnement utilisé pour cette opération : Unité, Boîte, Paquet, etc.",
                max_length=60,
            ),
        ),
        migrations.AddField(
            model_name="mouvementstock",
            name="quantite_par_conditionnement_mouvement",
            field=models.PositiveIntegerField(
                default=1,
                help_text="Nombre d’unités réelles contenues dans 1 conditionnement de l’opération.",
            ),
        ),
        migrations.AddField(
            model_name="mouvementstock",
            name="quantite_unites",
            field=models.PositiveIntegerField(
                default=1,
                help_text="Équivalent réel de l’opération en unités de base.",
            ),
        ),
        migrations.AddIndex(
            model_name="mouvementstock",
            index=models.Index(
                fields=["conditionnement_mouvement"],
                name="mouvements_s_conditionn_9c8a3f_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="mouvementstock",
            constraint=models.CheckConstraint(
                condition=models.Q(("quantite", 1), _connector="gte"),
                name="ck_mvt_stock_quantite_ge_1",
            ),
        ),
        migrations.AddConstraint(
            model_name="mouvementstock",
            constraint=models.CheckConstraint(
                condition=models.Q(("quantite_par_conditionnement_mouvement", 1), _connector="gte"),
                name="ck_mvt_stock_qpc_mvt_ge_1",
            ),
        ),
        migrations.AddConstraint(
            model_name="mouvementstock",
            constraint=models.CheckConstraint(
                condition=models.Q(("quantite_unites", 1), _connector="gte"),
                name="ck_mvt_stock_quantite_unites_ge_1",
            ),
        ),
    ]