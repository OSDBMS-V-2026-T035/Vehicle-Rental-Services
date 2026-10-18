from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bookings", "0003_handover_lifecycle")]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="payment_expires_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
