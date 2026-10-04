from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [("accounts", "0002_shopkeeperprofile_location")]

    operations = [
        migrations.CreateModel(
            name="Vehicle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("vehicle_type", models.CharField(choices=[("car", "Car"), ("bike", "Bike"), ("scooter", "Scooter"), ("cycle", "Cycle"), ("commercial", "Commercial")], max_length=20)),
                ("brand", models.CharField(max_length=80)),
                ("model_name", models.CharField(max_length=120)),
                ("registration_number", models.CharField(max_length=20, unique=True)),
                ("manufacturing_year", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1900), django.core.validators.MaxValueValidator(2100)])),
                ("daily_rate", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("seating_capacity", models.PositiveSmallIntegerField(default=2, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)])),
                ("description", models.TextField(blank=True)),
                ("image", models.FileField(blank=True, null=True, upload_to="vehicle-images/%Y/%m/")),
                ("is_available", models.BooleanField(default=True)),
                ("listing_status", models.CharField(choices=[("PENDING", "Pending review"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")], default="PENDING", max_length=20)),
                ("admin_note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("shopkeeper", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vehicles", to="accounts.shopkeeperprofile")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["vehicle_type", "listing_status", "is_available"], name="vehicles_ve_vehicle_342952_idx"),
                    models.Index(fields=["shopkeeper", "listing_status"], name="vehicles_ve_shopkee_05ade2_idx"),
                ],
            },
        ),
    ]
