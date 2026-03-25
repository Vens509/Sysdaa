from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("fournisseurs", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="articlefournisseur",
            name="date_livraison_prevue",
        ),
    ]