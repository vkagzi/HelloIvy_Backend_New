# Generated migration for adding metadata field to CareerSession

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("career_discovery", "0005_careersession_token_usage"),
    ]

    operations = [
        migrations.AddField(
            model_name="careersession",
            name="metadata",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Session metadata including pause/resume events",
            ),
        ),
    ]
