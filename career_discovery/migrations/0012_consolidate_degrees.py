from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("career_discovery", "0011_enhanced_report_sections"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="careerrecommendation",
            name="degree_pathways",
        ),
        migrations.RemoveField(
            model_name="careerrecommendation",
            name="degree_fit_scores",
        ),
        migrations.RemoveField(
            model_name="careerrecommendation",
            name="degree_decision_filter",
        ),
        migrations.AlterField(
            model_name="careerrecommendation",
            name="degrees",
            field=models.JSONField(
                default=list,
                help_text="Rich degree objects with fit scores, pathways, and decision filters",
            ),
        ),
    ]
