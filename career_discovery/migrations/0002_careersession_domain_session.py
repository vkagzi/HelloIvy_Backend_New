# Generated migration for adding domain_session to CareerSession

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('domain_discovery', '0001_initial'),
        ('career_discovery', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='careersession',
            name='domain_session',
            field=models.ForeignKey(
                blank=True,
                help_text='Reference to the Stream & Subject Selection session that preceded this Career & Degree Selection session',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='career_sessions',
                to='domain_discovery.domainsession'
            ),
        ),
    ]
