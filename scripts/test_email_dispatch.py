import sys
import os
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from utils.email import send_payment_pending_email, send_payment_success_email

def test_pending_email():
    print("\n--- Testing Pending Email ---")
    email = "ayushkumarsiani@gmail.com"
    modules = [
        {"name": "Career Discovery", "price": "₹999.00", "quantity": 1},
        {"name": "College Selector", "price": "₹4,500.58", "quantity": 2}
    ]
    try:
        send_payment_pending_email(
            email=email,
            user_name="Ayush (Test)",
            transaction_id="TEST_REF_123",
            payment_date="06 Jun 2026",
            modules=modules,
            total_amount="10,000.16",
            currency="INR"
        )
        print("Done. Check logs/email.")
    except Exception as e:
        print(f"Failed: {e}")

def test_success_email():
    print("\n--- Testing Success Email ---")
    email = "ayushkumarsiani@gmail.com"
    modules = [
        {"name": "Career Discovery", "price": "₹999.00", "quantity": 1}
    ]
    try:
        send_payment_success_email(
            email=email,
            user_name="Ayush (Test)",
            transaction_id="TEST_TXN_456",
            payment_date="06 Jun 2026",
            modules=modules,
            subtotal="₹999.00",
            tax="₹0.00",
            total_amount="₹999.00",
            currency="INR"
        )
        print("Done. Check logs/email.")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_pending_email()
    test_success_email()
