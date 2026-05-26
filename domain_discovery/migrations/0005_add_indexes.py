# Generated migration for adding database indexes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('domain_discovery', '0004_domainrecommendation_riasec_scores'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='domainmessage',
            index=models.Index(fields=['session', 'timestamp'], name='domain_disc_session_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='domainmessage',
            index=models.Index(fields=['session', 'type'], name='domain_disc_session_type_idx'),
        ),
    ]
