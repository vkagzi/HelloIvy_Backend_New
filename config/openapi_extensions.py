from drf_spectacular.extensions import OpenApiAuthenticationExtension
from openai import AzureOpenAI
from django.conf import settings

client = AzureOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_version="2024-02-15-preview"
)


class MyAuthenticationScheme(OpenApiAuthenticationExtension):  # type: ignore
    target_class = "apps.accounts.authentication.CustomJWTAuthentication"
    name = "Bearer Authentication"  # name used in the schema

    def get_security_definition(self, auto_schema):  # type: ignore
        return {
            "type": "http",
            "scheme": "bearer",
        }
