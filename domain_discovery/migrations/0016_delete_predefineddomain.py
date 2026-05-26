from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('domain_discovery', '0015_alter_domainsession_total_steps'),
    ]

    operations = [
        migrations.DeleteModel(
            name='PredefinedDomain',
        ),
    ]
