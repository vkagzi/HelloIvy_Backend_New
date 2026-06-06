import sys
import os
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from utils.invoice_pdf import InvoiceData, InvoiceLineItem, generate_invoice_pdf

def test_decimal_invoice():
    print("\n--- Testing Decimal Invoice ---")
    line_items = [
        InvoiceLineItem(module="Career Discovery", quantity=1, price=999.58),
        InvoiceLineItem(module="College Selector", quantity=2, price=4500.58)
    ]
    
    data = InvoiceData(
        order_id=999,
        order_date="06 Jun 2026",
        billing_name="Ayush Test",
        first_name="Ayush",
        last_name="Test",
        email="ayushkumarsiani@gmail.com",
        line_items=line_items,
        subtotal=999.58 + (4500.58 * 2),
        discount=0.0,
        tax=0.0,
        total=999.58 + (4500.58 * 2),
        currency="INR",
        transaction_id="TXN_DECIMAL_TEST",
        status="Completed",
        payment_mode="HDFC Gateway"
    )
    
    pdf_bytes = generate_invoice_pdf(data)
    if pdf_bytes:
        filename = "test_decimal_invoice.pdf"
        with open(filename, "wb") as f:
            f.write(pdf_bytes)
        print(f"Success! Saved to {filename}")
        print(f"Total Amount: {data.total}")
    else:
        print("Failed to generate PDF")

if __name__ == "__main__":
    test_decimal_invoice()
