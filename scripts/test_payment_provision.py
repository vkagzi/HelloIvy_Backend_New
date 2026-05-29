import sys
import os
import django
from django.utils import timezone

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from apps.accounts.models import UserPayment, User, UserModuleSubscription
from apps.accounts.payment_views import _provision_user_subscriptions, _send_payment_status_email

def run_test_scenario(name, modules_purchased):
    print(f"\n{'='*20} SCENARIO: {name} {'='*20}")
    email = "ayushkumarsiani@gmail.com"
    user, _ = User.objects.get_or_create(
        email=email,
        defaults={"first_name": "Ayush", "last_name": "Test"}
    )

    # 1. Create a dummy successful payment
    payment = UserPayment.objects.create(
        user=user,
        amount=999.00 * sum(d.get("quantity", 1) for d in modules_purchased),
        currency="INR",
        status=UserPayment.Status.COMPLETED,
        gateway_transaction_id=f"TXN_{timezone.now().timestamp()}",
        order_id=f"ORDER_{timezone.now().timestamp()}",
        modules_purchased=modules_purchased,
        metadata={"test": True}
    )
    
    print(f"--- 1. Testing Provisioning ---")
    _provision_user_subscriptions(payment)
    
    # Check what was unlocked for THIS payment
    subs = UserModuleSubscription.objects.filter(payment=payment)
    unlocked = [s.module_name for s in subs]
    print(f"Unlocked {len(unlocked)} records for {email}: {unlocked}")

    print(f"\n--- 2. Testing Email & Invoice ---")
    try:
        _send_payment_status_email(payment, "completed")
        print(f"Success flow triggered for {email}")
    except Exception as e:
        print(f"Flow failed: {e}")

def main():
    # Scenario 1: Same module (Quantity 2)
    run_test_scenario("Same Module (Qty 2)", [
        {"module": "college_selector", "quantity": 2}
    ])

    # Scenario 2: Different modules (Qty 1 each)
    run_test_scenario("Different Modules (Qty 1 each)", [
        {"module": "career_discovery", "quantity": 1},
        {"module": "college_selector", "quantity": 1}
    ])

    # Scenario 3: Mixed (Different modules and quantities)
    run_test_scenario("Mixed Modules and Quantities", [
        {"module": "career_discovery", "quantity": 2},
        {"module": "college_selector", "quantity": 1}
    ])

if __name__ == "__main__":
    main()

