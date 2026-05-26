"""
Django management command to create a user with email and password.

Usage:
    python manage.py create_user --email user@example.com --password securepassword123
    
Or with interactive prompts:
    python manage.py create_user
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError
from apps.accounts.models import User


class Command(BaseCommand):
    help = 'Creates a user with email and password. User will be active and can login immediately.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email address for the user',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password for the user',
        )
        parser.add_argument(
            '--terms-accepted',
            action='store_true',
            help='Mark terms as accepted',
        )

    def handle(self, *args, **options):
        email = options.get('email')
        password = options.get('password')
        terms_accepted = options.get('terms_accepted', False)

        # If email or password not provided via args, prompt for them
        if not email:
            email = input('Enter email address: ').strip()
        
        if not password:
            from getpass import getpass
            password = getpass('Enter password: ').strip()
            password_confirm = getpass('Confirm password: ').strip()
            
            if password != password_confirm:
                raise CommandError('Passwords do not match!')

        # Validate email
        if not email or '@' not in email:
            raise CommandError('Please provide a valid email address')

        # Validate password
        if not password or len(password) < 6:
            raise CommandError('Password must be at least 6 characters long')

        try:
            # Check if user already exists
            existing_user = User.objects.filter(email=email).first()
            
            if existing_user:
                self.stdout.write(
                    self.style.WARNING(f'User with email {email} already exists.')
                )
                update = input('Do you want to update the password? (yes/no): ').strip().lower()
                
                if update in ['yes', 'y']:
                    existing_user.set_password(password)
                    existing_user.is_active = True
                    if terms_accepted:
                        existing_user.accept_terms()
                    existing_user.save()
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ User {email} updated successfully!'
                        )
                    )
                    self.stdout.write(f'  - User is active: {existing_user.is_active}')
                    self.stdout.write(f'  - Terms accepted: {existing_user.terms_accepted}')
                else:
                    self.stdout.write(self.style.WARNING('Operation cancelled.'))
                return

            # Create new user
            user = User(email=email, is_active=True)
            user.set_password(password)
            user.save()
            
            if terms_accepted:
                user.accept_terms()

            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ User created successfully!'
                )
            )
            self.stdout.write(f'  - Email: {user.email}')
            self.stdout.write(f'  - ID: {user.id}')
            self.stdout.write(f'  - Active: {user.is_active}')
            self.stdout.write(f'  - Terms accepted: {user.terms_accepted}')
            self.stdout.write(f'  - Created at: {user.created_at}')
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nUser can now login with email: {email}'
                )
            )

        except IntegrityError as e:
            raise CommandError(f'Database error: {str(e)}')
        except Exception as e:
            raise CommandError(f'Error creating user: {str(e)}')
