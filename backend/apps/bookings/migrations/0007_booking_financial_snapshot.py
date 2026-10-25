from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bookings", "0006_booking_lifecycle_note_compatibility")]

    operations = [
        migrations.AddField(model_name="booking", name="commissionable_base", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.AddField(model_name="booking", name="tax_amount", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.AddField(model_name="booking", name="commission_rate", field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
        migrations.AddField(model_name="booking", name="platform_commission", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.AddField(model_name="booking", name="shopkeeper_net_earnings", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.AddField(model_name="booking", name="financial_calculation_version", field=models.PositiveSmallIntegerField(default=1)),
        migrations.AddField(model_name="booking", name="financial_confirmed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="booking", name="commission_reversed_at", field=models.DateTimeField(blank=True, null=True)),
    ]
