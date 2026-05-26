import os
import sys
import django

# Setup django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.urls import resolve, Resolver404
from django.test import RequestFactory
from rest_framework.test import APIRequestFactory
from domain_discovery.views import SubmitModuleReviewView
from apps.accounts.models import User

def test_resolve():
    print("Testing URL resolution:")
    try:
        match = resolve('/api/domain-discovery/submit-review/')
        print(f"URL resolved to view: {match.func.view_class.__name__}")
        print(f"URL name: {match.url_name}")
    except Resolver404:
        print("URL did not resolve!")
    
    print(f"User db_table: {User._meta.db_table}")
    print(f"User count in DB: {User.objects.count()}")

    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'domain_discovery_modulereview'::regclass;")
        constraints = cursor.fetchall()
        print("\nConstraints on domain_discovery_modulereview:")
        for name, definition in constraints:
            print(f"- {name}: {definition}")
        
        cursor.execute("SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'domain_discovery_domainsession'::regclass;")
        session_constraints = cursor.fetchall()
        print("\nConstraints on domain_discovery_domainsession:")
        for name, definition in session_constraints:
            print(f"- {name}: {definition}")

def test_view_post():
    print("\nTesting POST request on SubmitModuleReviewView:")
    from rest_framework.test import force_authenticate
    factory = APIRequestFactory()
    user, _ = User.objects.get_or_create(email="test_reviewer@example.com")
    request = factory.post('/api/domain-discovery/submit-review/', {'rating': 5, 'comment': 'Great experience!', 'module': 'stream'})
    
    # Authenticate using the DTO so is_authenticated is available
    force_authenticate(request, user=user.to_dto())
    
    # Resolve and execute view
    view = SubmitModuleReviewView.as_view()
    response = view(request)
    print(f"Status Code: {response.status_code}")
    print(f"Data: {response.data}")

if __name__ == '__main__':
    test_resolve()
    try:
        test_view_post()
    except Exception as e:
        print(f"Error executing view: {e}")
