import os
import django
import sys

# Set up Django environment
sys.path.append('c:/Users/ayush/Downloads/HelloIvy/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.accounts.models import User
from college_selector.models import CollegeSelectorSession
from college_selector.services import college_selector_service

def test_decoupling():
    # Find a test user
    user = User.objects.first()
    if not user:
        print("No users found to test with.")
        return

    print(f"Testing with user: {user.email}")
    
    # Try creating a college selector session directly
    try:
        session = college_selector_service.create_session(user=user)
        print(f"Successfully created College Selector session: {session.session_id}")
        # Clean up
        session.delete()
        print("Cleanup successful.")
    except Exception as e:
        print(f"FAILED to create session: {e}")

if __name__ == "__main__":
    test_decoupling()
