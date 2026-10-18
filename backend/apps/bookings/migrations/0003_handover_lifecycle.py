from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bookings", "0002_booking_email_verified_at_booking_renter_age_and_more")]

    operations = [
        migrations.AddField(model_name="booking", name="handover_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="booking", name="received_back_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="booking", name="shopkeeper_cancellation_reason", field=models.TextField(blank=True)),
        migrations.AlterField(model_name="booking", name="status", field=models.CharField(choices=[("PENDING", "Pending"), ("CONFIRMED", "Confirmed"), ("CANCELLED", "Cancelled"), ("COMPLETED", "Completed"), ("HANDED_OVER", "Vehicle handed over")], default="PENDING", max_length=20)),
    ]
