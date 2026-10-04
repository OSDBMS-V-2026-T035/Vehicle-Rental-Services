from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [("accounts", "0002_shopkeeperprofile_location"), ("vehicles", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Booking",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("pickup_date", models.DateField()),
                ("return_date", models.DateField()),
                ("total_amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("CONFIRMED", "Confirmed"), ("CANCELLED", "Cancelled"), ("COMPLETED", "Completed")], default="PENDING", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bookings", to=settings.AUTH_USER_MODEL)),
                ("vehicle", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bookings", to="vehicles.vehicle")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["vehicle", "pickup_date", "return_date", "status"], name="bookings_bo_vehicle_c02460_idx")],
                "constraints": [models.CheckConstraint(condition=models.Q(return_date__gte=models.F("pickup_date")), name="booking_return_after_pickup")],
            },
        ),
    ]
