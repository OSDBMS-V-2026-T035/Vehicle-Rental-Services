from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0007_user_permanent_ban")]

    operations = [
        migrations.AddField(model_name="shopkeeperprofile", name="legal_business_name", field=models.CharField(blank=True, max_length=160)),
        migrations.AddField(model_name="shopkeeperprofile", name="proprietor_name", field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name="shopkeeperprofile", name="business_type", field=models.CharField(blank=True, max_length=40)),
        migrations.AddField(model_name="shopkeeperprofile", name="gstin", field=models.CharField(blank=True, max_length=15)),
        migrations.AddField(model_name="shopkeeperprofile", name="pan_number", field=models.CharField(blank=True, max_length=10)),
        migrations.AddField(model_name="shopkeeperprofile", name="aadhaar_last4", field=models.CharField(blank=True, max_length=4)),
        migrations.AddField(model_name="shopkeeperprofile", name="business_registration_number", field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name="shopkeeperprofile", name="shop_photo", field=models.FileField(blank=True, null=True, upload_to="shop-documents/%Y/%m/")),
        migrations.AddField(model_name="shopkeeperprofile", name="address_proof", field=models.FileField(blank=True, null=True, upload_to="shop-documents/%Y/%m/")),
        migrations.AddField(model_name="shopkeeperprofile", name="pan_document", field=models.FileField(blank=True, null=True, upload_to="shop-documents/%Y/%m/")),
        migrations.AddField(model_name="shopkeeperprofile", name="aadhaar_document", field=models.FileField(blank=True, null=True, upload_to="shop-documents/%Y/%m/")),
        migrations.AddField(model_name="shopkeeperprofile", name="gst_certificate", field=models.FileField(blank=True, null=True, upload_to="shop-documents/%Y/%m/")),
        migrations.AddField(model_name="shopkeeperprofile", name="profile_completed_at", field=models.DateTimeField(blank=True, null=True)),
    ]
