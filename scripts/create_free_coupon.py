import os
import sys
import django

# Set up Django environment
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from apps.accounts.models import Coupon
from django.utils import timezone

def create_free_coupon():
    code = "FREE100"
    try:
        coupon = Coupon.objects.get(code=code)
        print(f"Coupon {code} already exists.")
    except Coupon.DoesNotExist:
        coupon = Coupon.objects.create(
            code=code,
            discount_type="percentage",
            discount_value=100,
            active=True,
            start_date=timezone.now(),
            expiry_date=None,  # No expiry
            limit_total=1000,
            limit_per_user=10,
        )
        print(f"Coupon {code} created successfully.")

if __name__ == "__main__":
    create_free_coupon()
