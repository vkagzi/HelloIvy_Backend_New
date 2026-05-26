# Generated migration for updating CareerSession total_steps to 20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('career_discovery', '0002_careersession_domain_session'),
    ]

    operations = [
        migrations.AlterField(
            model_name='careersession',
            name='total_steps',
            field=models.IntegerField(default=20),
        ),
    ]
