from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("payments", "0001_initial")]

    operations = [
        migrations.RenameIndex(
            model_name="paymenttransaction",
            old_name="payments_pa_custome_9fbd88_idx",
            new_name="payments_pa_custome_07a196_idx",
        ),
    ]
