# Generated migration for adding day_in_life, pros_and_cons, work_life_balance fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('career_discovery', '0006_careersession_metadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='careerrecommendation',
            name='day_in_life',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='careerrecommendation',
            name='pros_and_cons',
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='careerrecommendation',
            name='work_life_balance',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),
    ]
