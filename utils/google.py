"""
Google Gemini configuration utilities to avoid duplication across services
"""
import os
from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI, HarmCategory, HarmBlockThreshold
from google.oauth2 import service_account

def get_google_config():
    """
    Get Google Gemini configuration from settings or environment.
    
    Returns:
        dict: Configuration dictionary with google_api_key, project, location and model name
              
    Raises:
        ValueError: If required credentials are not configured
    """
    google_api_key = getattr(settings, 'GOOGLE_API_KEY', None) or os.getenv('GOOGLE_API_KEY')
    google_project = getattr(settings, 'GOOGLE_CLOUD_PROJECT', None) or os.getenv('GOOGLE_CLOUD_PROJECT')
    google_location = getattr(settings, 'GOOGLE_CLOUD_LOCATION', None) or os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
    google_model = getattr(settings, 'GOOGLE_MODEL', None) or os.getenv('GOOGLE_MODEL', 'gemini-1.5-flash')
    
    # Check if Vertex AI should be used
    use_vertex_env = os.getenv('GOOGLE_GENAI_USE_VERTEXAI', 'False').lower() == 'true'
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
    # Vertex AI is used if explicitly requested, or if no API key is provided but service account info exists
    use_vertex = use_vertex_env or (not google_api_key and (google_project or credentials_path))

    if not google_api_key and not use_vertex:
        raise ValueError("Google API credentials not configured. Set GOOGLE_API_KEY, GOOGLE_CLOUD_PROJECT, or GOOGLE_APPLICATION_CREDENTIALS.")

    credentials = None
    if use_vertex and credentials_path:
        # Strip quotes if present
        path = credentials_path.strip('"\'')
        credentials = service_account.Credentials.from_service_account_file(
            path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )

    return {
        'google_api_key': google_api_key if not use_vertex else None,
        'google_project': google_project,
        'google_location': google_location,
        'google_model': google_model,
        'use_vertex': use_vertex,
        'credentials': credentials,
    }


def create_google_chat_gemini(temperature: float = 0.7, max_tokens: int = 200) -> ChatGoogleGenerativeAI:
    """
    Create a ChatGoogleGenerativeAI instance with standard configuration,
    using Vertex AI backend if configured.
    
    Args:
        temperature: Temperature setting for the model (0.0-2.0)
        max_tokens: Maximum tokens for the response
        
    Returns:
        ChatGoogleGenerativeAI: Configured LLM instance
        
    Raises:
        ValueError: If Google API credentials are not configured
    """
    config = get_google_config()
    
    # Define safety settings to be more permissive to avoid empty responses
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    
    return ChatGoogleGenerativeAI(
        model=config['google_model'],
        google_api_key=config['google_api_key'],
        project=config['google_project'],
        location=config['google_location'],
        vertexai=config['use_vertex'],
        credentials=config['credentials'],
        temperature=temperature,
        max_output_tokens=max_tokens,
        safety_settings=safety_settings,
    )
