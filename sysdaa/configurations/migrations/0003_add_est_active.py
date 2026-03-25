from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("configurations", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="configurationsysteme",
            name="est_active",
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]