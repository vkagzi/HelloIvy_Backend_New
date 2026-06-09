from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, F
from apps.accounts.models import User, UserModuleSubscription
from utils.email import send_module_reminder_email
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Send weekly reminders to students who have not used their modules.'

    def handle(self, *args, **options):
        now = timezone.now()
        one_week_ago = now - timedelta(days=7)
        
        # 1. Find all active subscriptions
        # Filter for subscriptions where:
        # - Last reminder was more than a week ago OR never sent
        # - Subscription is active and not expired
        subscriptions = UserModuleSubscription.objects.filter(
            is_active=True,
            expiry_date__gte=now.date()
        ).filter(
            Q(reminder_last_sent_at__isnull=True) | 
            Q(reminder_last_sent_at__lte=one_week_ago)
        ).select_related('user')

        # To avoid multiple emails to the same user, group by user
        users_to_remind = {}
        for sub in subscriptions:
            if sub.user_id not in users_to_remind:
                users_to_remind[sub.user_id] = {
                    'user': sub.user,
                    'pending_modules': []
                }
            users_to_remind[sub.user_id]['pending_modules'].append(sub)

        count = 0
        for user_id, data in users_to_remind.items():
            user = data['user']
            pending_subs = data['pending_modules']
            
            # Check if ANY of the pending modules have been used
            unused_subs = []
            for sub in pending_subs:
                if not self._is_module_used(user, sub.module_name):
                    unused_subs.append(sub)
            
            if unused_subs:
                # Send one reminder for all unused modules
                try:
                    logger.info(f"Sending reminder to {user.email}")
                    send_module_reminder_email(user.email, user.first_name)
                    
                    # Update all unused subs for this user
                    for sub in unused_subs:
                        sub.reminder_last_sent_at = now
                        sub.reminder_count += 1
                        sub.save(update_fields=['reminder_last_sent_at', 'reminder_count'])
                    
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to send reminder to {user.email}: {e}")

        self.stdout.write(self.style.SUCCESS(f'Successfully sent reminders to {count} students.'))

    def _is_module_used(self, user, module_name) -> bool:
        """Check if the user has started a session for the given module."""
        try:
            if module_name == 'career_discovery':
                from career_discovery.models import CareerSession
                return CareerSession.objects.filter(user=user).exists()
            elif module_name == 'domain_discovery':
                from domain_discovery.models import DomainSession
                return DomainSession.objects.filter(user=user).exists()
            elif module_name == 'college_selector':
                from college_selector.models import CollegeSelectorSession
                return CollegeSelectorSession.objects.filter(user=user).exists()
        except ImportError:
            logger.warning(f"Could not import session model for {module_name}")
            return False
        return False
