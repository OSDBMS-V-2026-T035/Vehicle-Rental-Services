from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_rename_captcha_index")]

    operations = [
        migrations.AddField(
            model_name="shopkeeperprofile",
            name="shop_description",
            field=models.TextField(blank=True),
        ),
    ]
