"""
General-purpose TTS (Text-to-Speech) endpoint using Azure OpenAI.

Uses StreamingHttpResponse so audio chunks are forwarded to the client as
they arrive from the upstream TTS provider.  This dramatically reduces
time-to-first-audio on the client side.
"""
import logging

from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from utils.azure_openai import create_azure_openai_client

logger = logging.getLogger(__name__)


class TTSRequestSerializer(serializers.Serializer):
    text = serializers.CharField(required=True, max_length=4096)
    voice = serializers.ChoiceField(
        choices=['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'],
        default='nova',
        required=False,
    )
    speed = serializers.FloatField(default=1.0, min_value=0.25, max_value=4.0, required=False)


class GenerateSpeechView(APIView):
    """Generate speech from text using Azure OpenAI TTS (gpt-4o-mini-tts)."""
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        serializer = TTSRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        text = serializer.validated_data['text']
        voice = serializer.validated_data.get('voice', 'nova')
        speed = serializer.validated_data.get('speed', 1.0)

        # Eagerly validate configuration so we can return a proper error response
        # before we begin streaming.
        try:
            from django.conf import settings
            tts_deployment = getattr(settings, 'AZURE_OPENAI_TTS_DEPLOYMENT', 'gpt-4o-mini-tts')

            client = create_azure_openai_client(use_tts_endpoint=True)
        except Exception as e:
            return Response(
                {'error': f'TTS generation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        def audio_stream():
            with client.audio.speech.with_streaming_response.create(
                model=tts_deployment,
                voice=voice,
                input=text,
                speed=speed,
                response_format='mp3',
            ) as response:
                yield from response.iter_bytes(chunk_size=4096)

        http_response = StreamingHttpResponse(audio_stream(), content_type='audio/mpeg')
        http_response['Content-Disposition'] = 'inline; filename="speech.mp3"'
        http_response['Cache-Control'] = 'no-cache'
        return http_response
