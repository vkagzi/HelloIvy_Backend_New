"""
Drop orphaned tables from removed apps: interview_prep, essay_brainstorm, essay_evaluator.

Also cleans up their django_migrations history entries.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_add_settings_json_field"),
    ]

    operations = [
        # ── interview_prep ────────────────────────────────────
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS interview_responses CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS resume_analysis CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS interview_sessions CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ── essay_brainstorm ──────────────────────────────────
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_brainstorm_careerdiscoverymessage CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_brainstorm_careerdiscoverysession CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_brainstorm_conversationmessage CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_brainstorm_conversationsession CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_brainstorm_collegeselection CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_brainstorm_longtermgoal CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_brainstorm_shorttermgoal CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_brainstorm_professionalstory CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_brainstorm_personalstory CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_brainstorm_studentprofile CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_brainstorm_brainstormmessage CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_brainstorm_brainstormsession CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ── essay_evaluator ───────────────────────────────────
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_evaluator_essayhighlight CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_evaluator_analysisresult CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_evaluator_useressaystats CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_evaluator_essaytemplate CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS essay_evaluator_essaysubmission CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ── auth_user (no longer referenced) ──────────────────
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS auth_user_user_permissions CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS auth_user_groups CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS auth_user CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ── Clean up migration history ────────────────────────
        migrations.RunSQL(
            sql="DELETE FROM django_migrations WHERE app IN ('interview_prep', 'essay_brainstorm', 'essay_evaluator');",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
