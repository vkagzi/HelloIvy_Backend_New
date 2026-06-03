import os, sys, re
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.local"
import django
django.setup()

from apps.accounts.models import UserPayment
import requests

p = UserPayment.objects.filter(status="pending").first()
user = p.user
token = user.generate_token()

url = f"http://localhost:8000/api/accounts/me/payments/{p.id}/retry/"
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

print(f"Testing: POST {url}")
print(f"Payment ID: {p.id}, Status: {p.status}, Amount: {p.amount}")
print()

r = requests.post(url, headers=headers, json={})
print("HTTP Status:", r.status_code)
print()

if r.status_code != 200:
    text = r.text
    # Try to get JSON error first
    try:
        import json
        data = json.loads(text)
        print("JSON Error:", data)
    except Exception:
        # Parse Django debug HTML
        m1 = re.search(r'exception_value.*?<pre[^>]*>(.*?)</pre>', text, re.DOTALL)
        m2 = re.search(r'exception_type.*?<pre[^>]*>(.*?)</pre>', text, re.DOTALL)
        if m2:
            print("Exception Type:", re.sub(r'<[^>]+>', '', m2.group(1)).strip())
        if m1:
            print("Exception:", re.sub(r'<[^>]+>', '', m1.group(1)).strip())
        
        # Get traceback lines
        tb_parts = re.findall(r'<span class="fname">(.*?)</span>.*?in <span class="function">(.*?)</span>.*?<pre class="highlight">(.*?)</pre>', text, re.DOTALL)
        print("\nTraceback:")
        for fname, func, code in tb_parts[-5:]:
            print(f"  File: {fname.strip()}, in {func.strip()}")
            print(f"    {re.sub(chr(10), ' ', re.sub(r'<[^>]+>', '', code.strip()))[:150]}")
else:
    print("Success:", r.json())
