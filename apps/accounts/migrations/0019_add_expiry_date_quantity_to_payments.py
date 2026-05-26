from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0018_populate_user_names_from_profile"),
    ]

    operations = [
        migrations.AddField(
            model_name="userpayment",
            name="expiry_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="userpayment",
            name="quantity",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="schoolpayment",
            name="expiry_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="schoolpayment",
            name="quantity",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
