# Generated migration for adding medium field to DomainMessage

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('domain_discovery', '0017_alter_domainsession_total_steps'),
    ]

    operations = [
        migrations.AddField(
            model_name='domainmessage',
            name='medium',
            field=models.CharField(
                choices=[('text', 'Text'), ('voice', 'Voice')],
                default='text',
                max_length=10,
            ),
        ),
    ]
