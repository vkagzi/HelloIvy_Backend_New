from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0015_unique_pending_payment_constraints"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("student", "Student"),
                    ("superadmin", "Superadmin"),
                    ("operationadmin", "Operation Admin"),
                    ("schooladmin", "School Admin"),
                    ("schoolopsadmin", "School Ops Admin"),
                ],
                default="student",
                max_length=20,
            ),
        ),
    ]
