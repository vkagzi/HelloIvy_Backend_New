"""
Management command to regenerate domain recommendations for existing sessions.
This will update recommendations with all the required fields.

Usage:
    python manage.py regenerate_domain_recommendations
    python manage.py regenerate_domain_recommendations --session-id <session_id>
"""
from django.core.management.base import BaseCommand
from domain_discovery.models import DomainSession, DomainRecommendation
from domain_discovery.services import DomainDiscoveryService


class Command(BaseCommand):
    help = 'Regenerate domain recommendations to include all required fields'

    def add_arguments(self, parser):
        parser.add_argument(
            '--session-id',
            type=str,
            help='Specific session ID to regenerate recommendations for',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Regenerate recommendations for all sessions',
        )

    def handle(self, *args, **options):
        service = DomainDiscoveryService()
        
        if options['session_id']:
            # Regenerate for specific session
            try:
                session = DomainSession.objects.get(session_id=options['session_id'])
                self.stdout.write(f"Regenerating recommendations for session {session.session_id}...")
                
                # Delete existing recommendations
                DomainRecommendation.objects.filter(session=session).delete()
                
                # Generate new recommendations
                recommendations = service.generate_recommendations(session)
                
                self.stdout.write(self.style.SUCCESS(
                    f'Successfully regenerated {len(recommendations)} recommendations for session {session.session_id}'
                ))
                
                # Display what was generated
                for rec in recommendations:
                    self.stdout.write(f"  - {rec.domain_title} ({rec.match_percentage}%)")
                    self.stdout.write(f"    Key Interests: {len(rec.key_interests)} items")
                    self.stdout.write(f"    Sub-Domains: {len(rec.sub_domains)} items")
                    self.stdout.write(f"    Related Subjects: {len(rec.related_subjects)} items")
                    self.stdout.write(f"    Exploration Activities: {len(rec.exploration_activities)} items")
                    self.stdout.write(f"    Potential Careers: {len(rec.potential_careers)} items")
                
            except DomainSession.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f'Session {options["session_id"]} not found'
                ))
        
        elif options['all']:
            # Regenerate for all sessions
            sessions = DomainSession.objects.filter(is_active=False)
            total = sessions.count()
            
            self.stdout.write(f"Found {total} completed sessions to process...")
            
            success_count = 0
            error_count = 0
            
            for session in sessions:
                try:
                    self.stdout.write(f"Processing session {session.session_id}...")
                    
                    # Delete existing recommendations
                    DomainRecommendation.objects.filter(session=session).delete()
                    
                    # Generate new recommendations
                    recommendations = service.generate_recommendations(session)
                    
                    if recommendations:
                        success_count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f'  ✓ Generated {len(recommendations)} recommendations'
                        ))
                    else:
                        error_count += 1
                        self.stdout.write(self.style.WARNING(
                            f'  ! No recommendations generated'
                        ))
                
                except Exception as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(
                        f'  ✗ Error: {str(e)}'
                    ))
            
            self.stdout.write(self.style.SUCCESS(
                f'\nCompleted: {success_count} successful, {error_count} errors out of {total} sessions'
            ))
        
        else:
            self.stdout.write(self.style.WARNING(
                'Please specify either --session-id <id> or --all'
            ))
