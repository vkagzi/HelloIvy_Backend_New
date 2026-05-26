# Generated migration for updating DomainSession total_steps to 20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('domain_discovery', '0002_predefineddomain'),
    ]

    operations = [
        migrations.AlterField(
            model_name='domainsession',
            name='total_steps',
            field=models.IntegerField(default=20),
        ),
    ]
