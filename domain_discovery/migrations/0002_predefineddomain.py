# Generated migration for adding PredefinedDomain model

from django.db import migrations, models


def create_predefined_domains(apps, schema_editor):
    """Create the 13 predefined domains"""
    PredefinedDomain = apps.get_model('domain_discovery', 'PredefinedDomain')
    
    domains = [
        {
            'title': 'Pure Science',
            'description': 'Enjoying science research, logic, and problem-solving',
            'order': 1
        },
        {
            'title': 'Arts',
            'description': 'Enjoying creative expression through art, music, design, or performance',
            'order': 2
        },
        {
            'title': 'Humanities',
            'description': 'Enjoying reading, writing, ideas, culture, and understanding people',
            'order': 3
        },
        {
            'title': 'Business',
            'description': 'Enjoying leadership, decision-making, teamwork, and strategy',
            'order': 4
        },
        {
            'title': 'Finance',
            'description': 'Enjoying numbers, analysis, patterns, and structured thinking',
            'order': 5
        },
        {
            'title': 'Entrepreneurship',
            'description': 'Enjoying building ideas, taking initiative, creating something new',
            'order': 6
        },
        {
            'title': 'Law',
            'description': 'Enjoying debate, reasoning, rules, justice, and critical thinking',
            'order': 7
        },
        {
            'title': 'Social Sciences',
            'description': 'Enjoying understanding human behaviour, society, research, and impact',
            'order': 8
        },
        {
            'title': 'Health & Life Science',
            'description': 'Enjoying biology, health, human life, and helping people through science',
            'order': 9
        },
        {
            'title': 'Sports/Athletics',
            'description': 'Enjoying physical activity, competition, discipline, teamwork, resilience, and improving performance through training, strategy, and measurable goals',
            'order': 10
        },
        {
            'title': 'Engineering & Applied Technology',
            'description': 'Enjoys designing systems, machines, software, infrastructure',
            'order': 11
        },
        {
            'title': 'Design & Aesthetics (Creative Problem-Solving)',
            'description': 'Enjoys improving usability, elegance, and experience',
            'order': 12
        },
        {
            'title': 'Public Policy, Governance & Impact',
            'description': 'Enjoys balancing ethics, economics, and feasibility',
            'order': 13
        },
    ]
    
    for domain_data in domains:
        PredefinedDomain.objects.create(
            title=domain_data['title'],
            description=domain_data['description'],
            order=domain_data['order'],
            is_active=True
        )


def remove_predefined_domains(apps, schema_editor):
    """Remove all predefined domains"""
    PredefinedDomain = apps.get_model('domain_discovery', 'PredefinedDomain')
    PredefinedDomain.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('domain_discovery', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PredefinedDomain',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, unique=True)),
                ('description', models.TextField()),
                ('is_active', models.BooleanField(default=True)),
                ('order', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Predefined Domain',
                'verbose_name_plural': 'Predefined Domains',
                'ordering': ['order', 'title'],
            },
        ),
        migrations.RunPython(create_predefined_domains, remove_predefined_domains),
    ]
