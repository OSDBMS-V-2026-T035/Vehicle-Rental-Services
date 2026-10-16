import hashlib

from django.db import migrations, models


def populate_notification_keys(apps, schema_editor):
    Notification = apps.get_model("notifications", "Notification")
    seen = set()
    for notice in Notification.objects.order_by("id").iterator():
        key = hashlib.sha256(f"{notice.title}\n{notice.message}".encode("utf-8")).hexdigest()
        pair = (notice.user_id, key)
        # Preserve legacy duplicate rows until the user explicitly removes an account,
        # while ensuring new events use a unique key from this migration onward.
        if pair in seen:
            key = f"legacy-{notice.id}"
        seen.add(pair)
        notice.dedupe_key = key
        notice.save(update_fields=["dedupe_key"])


class Migration(migrations.Migration):
    dependencies = [("notifications", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="dedupe_key",
            field=models.CharField(default="", editable=False, max_length=64),
        ),
        migrations.RunPython(populate_notification_keys, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(fields=("user", "dedupe_key"), name="unique_user_notification_dedupe_key"),
        ),
    ]
