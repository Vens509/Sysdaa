from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0004_alter_auditlog_action"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditlog",
            name="identifiant_saisi",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["identifiant_saisi"], name="audit_audit_identif_6f4f2d_idx"),
        ),
    ]