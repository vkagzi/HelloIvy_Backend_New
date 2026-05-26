# Generated manually on 2026-04-01

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_migrate_school_role_to_schooladmin"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserModuleSubscription",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                ("expiry_date", models.DateField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscriptions",
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "unique_together": {("user", "module_name")},
            },
        ),
    ]
