import os
import environ
from openai import AzureOpenAI
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

try:
    api_key = env("AZURE_OPENAI_API_KEY")
    endpoint = env("AZURE_OPENAI_ENDPOINT")
    deployment = env("AZURE_OPENAI_DEPLOYMENT")
    
    print(f"Testing Azure OpenAI with deployment: {deployment}")
    
    client = AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version="2024-02-15-preview"
    )

    response = client.chat.completions.create(
        model=deployment,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": "Return a JSON with a key 'message' and value 'hello'"}
        ],
        temperature=0
    )
    print("Success!")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Failed: {e}")
