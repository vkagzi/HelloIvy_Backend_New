import os
import sys
import django

# Set up Django environment
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from apps.accounts.models import UserPayment
from apps.accounts.payment_views import _generate_payment_invoice

def debug_payment(payment_id):
    print(f"Debugging payment_id={payment_id}")
    try:
        payment = UserPayment.objects.get(id=payment_id)
        print(f"Found payment: status={payment.status}, amount={payment.amount}, modules={payment.modules_purchased}")
        
        pdf_bytes = _generate_payment_invoice(payment)
        if pdf_bytes:
            print(f"SUCCESS: Generated {len(pdf_bytes)} bytes of PDF")
        else:
            print("FAILURE: _generate_payment_invoice returned None (check logic)")
            
    except UserPayment.DoesNotExist:
        print(f"ERROR: Payment {payment_id} not found")
    except Exception as e:
        import traceback
        print(f"ERROR during debugging: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        debug_payment(int(sys.argv[1]))
    else:
        print("Usage: python scripts/debug_invoice.py <payment_id>")
