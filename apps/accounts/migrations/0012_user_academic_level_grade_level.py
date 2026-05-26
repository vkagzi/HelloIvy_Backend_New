from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_alter_schoolpayment_id_alter_userpayment_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="academic_level",
            field=models.CharField(
                blank=True,
                choices=[
                    ("high_school", "High School (8th–12th grade)"),
                    ("undergraduate", "College/Undergraduate"),
                    ("postgraduate", "Postgraduate/Master's"),
                    ("professional", "Working Professional"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="grade_level",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
