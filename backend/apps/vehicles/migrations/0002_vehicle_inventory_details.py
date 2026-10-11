from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [("accounts", "0006_shopkeeperprofile_shop_description"), ("vehicles", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="available_quantity",
            field=models.PositiveSmallIntegerField(
                default=1,
                validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(999)],
            ),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="body_style",
            field=models.CharField(blank=True, default="standard", max_length=40),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="fuel_capacity",
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="fuel_type",
            field=models.CharField(default="petrol", max_length=20),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="quantity",
            field=models.PositiveSmallIntegerField(
                default=1,
                validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(999)],
            ),
        ),
        migrations.AddConstraint(
            model_name="vehicle",
            constraint=models.CheckConstraint(
                condition=models.Q(available_quantity__lte=models.F("quantity")),
                name="vehicle_available_units_lte_quantity",
            ),
        ),
    ]
