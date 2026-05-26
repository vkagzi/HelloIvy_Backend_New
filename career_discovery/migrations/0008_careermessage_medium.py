# Generated migration for adding medium field to CareerMessage

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('career_discovery', '0007_careerrecommendation_day_in_life_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='careermessage',
            name='medium',
            field=models.CharField(
                choices=[('text', 'Text'), ('voice', 'Voice')],
                default='text',
                max_length=10,
            ),
        ),
    ]
