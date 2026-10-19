from django.db import migrations, models


def repair_lifecycle_note_column(apps, schema_editor):
    """Reconcile local databases created by the pre-migration lifecycle build."""
    table_name = "bookings_booking"
    with schema_editor.connection.cursor() as cursor:
        columns = {
            row[0]
            for row in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }
    quoted_table = schema_editor.quote_name(table_name)
    quoted_column = schema_editor.quote_name("lifecycle_note")
    if "lifecycle_note" in columns and schema_editor.connection.vendor == "mysql":
        schema_editor.execute(
            f"ALTER TABLE {quoted_table} MODIFY COLUMN {quoted_column} varchar(255) NOT NULL DEFAULT ''"
        )
    elif "lifecycle_note" not in columns:
        schema_editor.execute(
            f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} varchar(255) NOT NULL DEFAULT ''"
        )


class Migration(migrations.Migration):
    dependencies = [("bookings", "0005_bookinginspection")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(repair_lifecycle_note_column, migrations.RunPython.noop)],
            state_operations=[
                migrations.AddField(
                    model_name="booking",
                    name="lifecycle_note",
                    field=models.CharField(blank=True, default="", max_length=255),
                ),
            ],
        ),
    ]
