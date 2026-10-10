from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_shopkeeperprofile_statuses")]
    operations = [
        migrations.CreateModel(
            name="CaptchaChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("challenge_id", models.CharField(max_length=128, unique=True)),
                ("answer_hash", models.CharField(max_length=128)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(model_name="captchachallenge", index=models.Index(fields=["challenge_id", "expires_at"], name="accounts_ca_challen_3ddc10_idx")),
    ]
