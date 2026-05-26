# Generated migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('domain_discovery', '0011_alter_domainsession_total_steps'),
    ]

    operations = [
        migrations.AddField(
            model_name='domainsession',
            name='notes',
            field=models.TextField(
                blank=True,
                default='',
                help_text="AI-generated observations and insights about the student's profile to guide the conversation",
            ),
        ),
    ]
