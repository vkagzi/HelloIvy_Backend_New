"""
Azure OpenAI configuration utilities to avoid duplication across services.
Uses Azure's OpenAI-compatible GA API (no api_version required).
"""
from django.conf import settings
from langchain_openai import ChatOpenAI
from openai import OpenAI


def get_azure_openai_config():
    """
    Get Azure OpenAI configuration from settings or environment.

    Returns:
        dict: Configuration dictionary with base_url, azure_api_key, and azure_deployment.
              base_url is constructed as:
              {azure_endpoint}/openai/v1/

    Raises:
        ValueError: If required credentials are not configured
    """
    azure_endpoint = getattr(settings, 'AZURE_OPENAI_ENDPOINT', None)
    azure_api_key = getattr(settings, 'AZURE_OPENAI_API_KEY', None)
    azure_deployment = getattr(settings, 'AZURE_OPENAI_DEPLOYMENT', None)

    azure_tts_endpoint = getattr(settings, 'AZURE_OPENAI_TTS_ENDPOINT', None) or azure_endpoint
    azure_tts_api_key = getattr(settings, 'AZURE_OPENAI_TTS_API_KEY', None) or azure_api_key
    azure_tts_deployment = getattr(settings, 'AZURE_OPENAI_TTS_DEPLOYMENT', 'gpt-4o-mini-tts')
    use_responses_api = getattr(settings, 'AZURE_OPENAI_USE_RESPONSES_API', True)

    if not azure_endpoint or not azure_api_key:
        raise ValueError("Azure OpenAI credentials not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY.")

    # Azure's OpenAI-compatible GA endpoint — no api_version needed
    base_url = f"{azure_endpoint.rstrip('/')}/openai/v1/"
    azure_tts_base_url = f"{azure_tts_endpoint.rstrip('/')}/openai/v1/"

    return {
        'base_url': base_url,
        'azure_api_key': azure_api_key,
        'azure_deployment': azure_deployment,
        'azure_tts_base_url': azure_tts_base_url,
        'azure_tts_api_key': azure_tts_api_key,
        'azure_tts_deployment': azure_tts_deployment,
        'use_responses_api': use_responses_api,
    }


def create_azure_openai_client(use_tts_endpoint: bool = False) -> OpenAI:
    """
    Create a raw OpenAI client pointed at Azure's OpenAI-compatible GA API.

    Args:
        use_tts_endpoint: If True, use the TTS-specific endpoint/key; otherwise use the main endpoint.

    Returns:
        OpenAI: Configured OpenAI client instance

    Raises:
        ValueError: If Azure OpenAI credentials are not configured
    """
    config = get_azure_openai_config()

    if use_tts_endpoint:
        base_url = config['azure_tts_base_url']
        api_key = config['azure_tts_api_key']
    else:
        base_url = config['base_url']
        api_key = config['azure_api_key']

    return OpenAI(base_url=base_url, api_key=api_key)


def create_azure_chat_openai(temperature: float = 0.7, max_tokens: int = 200, reasoning_effort: str = None) -> ChatOpenAI:
    """
    Create a ChatOpenAI instance pointed at Azure's OpenAI-compatible GA API.

    Args:
        temperature: Temperature setting for the model (0.0-1.0)
        max_tokens: Maximum tokens for the response
        reasoning_effort: Reasoning effort level ('low', 'medium', 'high'). Only applies to o-series models.

    Returns:
        ChatOpenAI: Configured LLM instance

    Raises:
        ValueError: If Azure OpenAI credentials are not configured
    """
    config = get_azure_openai_config()

    kwargs = dict(
        base_url=config['base_url'],
        api_key=config['azure_api_key'],
        model=config['azure_deployment'],
        max_tokens=max_tokens,
        use_responses_api=config['use_responses_api'],
    )
    if reasoning_effort is not None:
        kwargs['reasoning_effort'] = reasoning_effort
    else:
        kwargs['temperature'] = temperature

    return ChatOpenAI(**kwargs)
