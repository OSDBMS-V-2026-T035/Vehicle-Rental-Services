from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("bookings", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency", models.CharField(default="INR", max_length=3)),
                ("status", models.CharField(choices=[("PENDING", "Pending payment"), ("PAID", "Paid"), ("FAILED", "Failed"), ("REFUNDED", "Refunded"), ("CANCELLED", "Cancelled")], default="PENDING", max_length=16)),
                ("provider", models.CharField(blank=True, max_length=40)),
                ("provider_reference", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("booking", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="payment", to="bookings.booking")),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payment_transactions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(model_name="paymenttransaction", index=models.Index(fields=["customer", "status", "created_at"], name="payments_pa_custome_9fbd88_idx")),
    ]
