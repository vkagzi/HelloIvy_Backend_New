# Generated migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('career_discovery', '0003_alter_careersession_total_steps'),
    ]

    operations = [
        migrations.AddField(
            model_name='careersession',
            name='notes',
            field=models.TextField(
                blank=True,
                default='',
                help_text="AI-generated observations about the student derived from profile and Stream & Subject Selection context to guide career exploration",
            ),
        ),
    ]
