from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0006_shopkeeperprofile_shop_description")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_permanently_banned",
            field=models.BooleanField(default=False),
        ),
    ]
