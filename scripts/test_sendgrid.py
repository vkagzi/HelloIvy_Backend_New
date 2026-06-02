import os
import sys
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

def test_sendgrid(api_key):
    print(f"Testing API key: {api_key[:10]}...")
    sg = SendGridAPIClient(api_key)
    try:
        # We don't actually need to send an email to test the key
        # We can just check the scopes or something similar, but sending a test email is more definitive
        message = Mail(
            from_email='outreach@reachivy.com',
            to_emails='ayush@reachivy.com',
            subject='SendGrid Test',
            plain_text_content='Test content'
        )
        response = sg.send(message)
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {response.headers}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        key = sys.argv[1]
    else:
        # Try to load from .env
        from dotenv import load_dotenv
        load_dotenv()
        key = os.getenv("SENDGRID_API_KEY")
    
    if not key:
        print("No API key found.")
    else:
        test_sendgrid(key)
