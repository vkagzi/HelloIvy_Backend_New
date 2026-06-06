import requests
import json
import sys

# Replace with a valid session ID if possible, or just hit the endpoint to see the error
SESSION_ID = "domain_065085fa01f6" 
URL = f"http://127.0.0.1:8000/api/domain-discovery/{SESSION_ID}/messages/stream/"

# Mock auth headers if needed, but the view has permission_classes = [] in my recent view
# Wait, let me check permission_classes again.
headers = {
    'Content-Type': 'application/json'
}

data = {
    'content': 'hello'    
}

try:
    print(f"Testing URL: {URL}")
    response = requests.post(URL, json=data, headers=headers, stream=True)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code != 200:
        print(f"Error Response Body (first 500 chars): {response.text[:500]}")
        with open("debug_error.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("Full error saved to debug_error.html")
        sys.exit(1)
        
    print("Streaming started:")
    for line in response.iter_lines():
        if line:
            print(f"Chunk: {line.decode('utf-8')}")
            
except Exception as e:
    print(f"Request failed: {e}")
