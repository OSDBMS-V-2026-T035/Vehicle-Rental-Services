from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_captchachallenge")]
    operations = [
        migrations.RenameIndex(
            model_name="captchachallenge",
            new_name="accounts_ca_challen_9a36ca_idx",
            old_name="accounts_ca_challen_3ddc10_idx",
        ),
    ]
