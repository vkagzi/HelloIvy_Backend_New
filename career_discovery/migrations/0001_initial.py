# Generated migration for career_discovery models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CareerSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.CharField(db_index=True, max_length=100, unique=True)),
                ('current_step', models.IntegerField(default=0)),
                ('total_steps', models.IntegerField(default=10)),
                ('current_phase', models.CharField(choices=[('profile', 'Profile Builder'), ('explorer', 'Career Explorer')], default='profile', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='career_sessions', to='accounts.user')),
            ],
            options={
                'verbose_name': 'Career Session',
                'verbose_name_plural': 'Career Sessions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CareerRecommendation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('career_title', models.CharField(max_length=200)),
                ('salary_range', models.CharField(blank=True, max_length=100)),
                ('match_percentage', models.IntegerField(default=0)),
                ('required_skills', models.JSONField(default=list)),
                ('next_steps', models.JSONField(default=list)),
                ('description', models.TextField(blank=True)),
                ('why_recommended', models.TextField(blank=True)),
                ('alignment_points', models.JSONField(default=list)),
                ('rank', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recommendations', to='career_discovery.careersession')),
            ],
            options={
                'verbose_name': 'Career Recommendation',
                'verbose_name_plural': 'Career Recommendations',
                'ordering': ['rank', '-match_percentage'],
            },
        ),
        migrations.CreateModel(
            name='CareerMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message_id', models.CharField(max_length=100, unique=True)),
                ('type', models.CharField(choices=[('bot', 'Bot'), ('user', 'User')], max_length=10)),
                ('content', models.TextField()),
                ('step_number', models.IntegerField(default=0)),
                ('phase', models.CharField(default='profile', max_length=20)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='career_discovery.careersession')),
            ],
            options={
                'verbose_name': 'Career Message',
                'verbose_name_plural': 'Career Messages',
                'ordering': ['timestamp'],
            },
        ),
    ]
