from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_shopkeeperprofile_location")]

    operations = [
        migrations.AlterField(
            model_name="shopkeeperprofile",
            name="verification_status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"), ("VERIFIED", "Verified"),
                    ("REJECTED", "Rejected"), ("REVOKED", "Revoked"),
                ],
                default="PENDING",
                max_length=20,
            ),
        ),
    ]
