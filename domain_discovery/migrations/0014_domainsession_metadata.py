# Generated migration for adding metadata field to DomainSession

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("domain_discovery", "0013_domainsession_token_usage"),
    ]

    operations = [
        migrations.AddField(
            model_name="domainsession",
            name="metadata",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Session metadata updated by background conclusion check: should_conclude, pending_topics, etc.",
            ),
        ),
    ]
