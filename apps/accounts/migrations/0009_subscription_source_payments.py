from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_user_module_access"),
    ]

    operations = [
        # Add source field to SchoolModuleSubscription
        migrations.AddField(
            model_name="schoolmodulesubscription",
            name="source",
            field=models.CharField(
                choices=[("admin", "Admin"), ("payment", "Payment"), ("other", "Other")],
                default="admin",
                max_length=20,
            ),
        ),
        # Add source field to UserModuleSubscription
        migrations.AddField(
            model_name="usermodulesubscription",
            name="source",
            field=models.CharField(
                choices=[("admin", "Admin"), ("payment", "Payment"), ("other", "Other")],
                default="admin",
                max_length=20,
            ),
        ),
        # Create UserPayment model
        migrations.CreateModel(
            name="UserPayment",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="accounts.user",
                    ),
                ),
                (
                    "module_name",
                    models.CharField(
                        choices=[
                            ("essay_brainstormer", "Essay Brainstormer"),
                            ("essay_evaluator", "Essay Evaluator"),
                            ("college_selector", "College Selector"),
                            ("degree_selector", "Degree Selector"),
                            ("interview_prep", "Interview Prep"),
                            ("resume_builder", "Resume Builder"),
                            ("career_discovery", "Career Discovery"),
                            ("domain_discovery", "Domain Discovery"),
                        ],
                        max_length=30,
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency", models.CharField(default="USD", max_length=10)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("refunded", "Refunded"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("payment_gateway", models.CharField(blank=True, default="", max_length=50)),
                ("gateway_transaction_id", models.CharField(blank=True, default="", max_length=200)),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        # Create SchoolPayment model
        migrations.CreateModel(
            name="SchoolPayment",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="accounts.school",
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency", models.CharField(default="USD", max_length=10)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("refunded", "Refunded"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("payment_gateway", models.CharField(blank=True, default="", max_length=50)),
                ("gateway_transaction_id", models.CharField(blank=True, default="", max_length=200)),
                ("modules_purchased", models.JSONField(blank=True, default=list)),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
