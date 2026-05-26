from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_subscription_source_payments"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="userpayment",
            name="module_name",
        ),
        migrations.AddField(
            model_name="userpayment",
            name="modules_purchased",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
