from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0029_alter_grademoduleautoassignment_module_name_and_more"),
    ]

    operations = [
        # Add order_id column to UserPayment
        migrations.AddField(
            model_name="userpayment",
            name="order_id",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        # Add order_id column to SchoolPayment
        migrations.AddField(
            model_name="schoolpayment",
            name="order_id",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        # Remove unique-pending-per-user constraint
        migrations.RemoveConstraint(
            model_name="userpayment",
            name="unique_pending_user_payment",
        ),
        # Remove unique-pending-per-school constraint
        migrations.RemoveConstraint(
            model_name="schoolpayment",
            name="unique_pending_school_payment",
        ),
    ]
