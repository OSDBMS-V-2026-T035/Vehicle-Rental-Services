from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("vehicles", "0002_vehicle_inventory_details")]

    operations = [
        migrations.AddField(model_name="vehicle", name="rc_number", field=models.CharField(blank=True, max_length=40)),
        migrations.AddField(model_name="vehicle", name="rc_document", field=models.FileField(blank=True, null=True, upload_to="vehicle-documents/%Y/%m/")),
        migrations.AddField(model_name="vehicle", name="insurance_document", field=models.FileField(blank=True, null=True, upload_to="vehicle-documents/%Y/%m/")),
        migrations.AddField(model_name="vehicle", name="insurance_policy_number", field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name="vehicle", name="insurance_expiry_date", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="vehicle", name="puc_document", field=models.FileField(blank=True, null=True, upload_to="vehicle-documents/%Y/%m/")),
        migrations.AddField(model_name="vehicle", name="puc_expiry_date", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="vehicle", name="vehicle_photo_front", field=models.FileField(blank=True, null=True, upload_to="vehicle-images/%Y/%m/")),
        migrations.AddField(model_name="vehicle", name="vehicle_photo_rear", field=models.FileField(blank=True, null=True, upload_to="vehicle-images/%Y/%m/")),
        migrations.AddField(model_name="vehicle", name="vehicle_photo_left", field=models.FileField(blank=True, null=True, upload_to="vehicle-images/%Y/%m/")),
        migrations.AddField(model_name="vehicle", name="vehicle_photo_right", field=models.FileField(blank=True, null=True, upload_to="vehicle-images/%Y/%m/")),
    ]
