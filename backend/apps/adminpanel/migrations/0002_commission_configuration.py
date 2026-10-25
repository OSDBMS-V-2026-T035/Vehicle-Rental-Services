from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("adminpanel", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="CommissionConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("commission_rate", models.DecimalField(decimal_places=2, max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="commission_configuration_updates", to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [models.CheckConstraint(condition=models.Q(("commission_rate__gte", 0), ("commission_rate__lte", 100)), name="commission_rate_between_zero_and_hundred")]},
        ),
    ]
