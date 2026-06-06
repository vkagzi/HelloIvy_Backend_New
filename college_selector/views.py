"""
College Selector API Views
"""
import jwt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from datetime import datetime
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import models
from django.http import HttpResponse, StreamingHttpResponse
import json
import threading
import queue
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.accounts.models import User
from utils.jwt import JWT_SECRET_KEY, ALGORITHM
from .models import CollegeSelectorSession, CollegeSelectorMessage, CollegeRecommendation
from .serializers import (
    CollegeSelectorSessionSerializer,
    CollegeSelectorSessionBasicSerializer,
    CollegeSelectorMessageSerializer,
    CollegeRecommendationSerializer,
    SavePreferencesRequestSerializer,
    SendMessageRequestSerializer,
    SendMessageResponseSerializer,
    TranscribeAudioRequestSerializer,
    TranscribeAudioResponseSerializer,
    GenerateSpeechRequestSerializer,
    TranscriptSerializer,
)
from .services import college_selector_service
from .constants import DEGREE_LEVELS, DEGREE_TYPES_BY_LEVEL
from apps.profiles.services import calculate_profile_completion
from utils.profile_helpers import get_user_profile_data
from utils.user_helpers import get_user_instance
from domain_discovery.models import DomainSession
from career_discovery.models import CareerSession
from utils.azure_openai import create_azure_openai_client
from django.utils import timezone
from utils.profile_formatting import format_user_profile_context
from utils.email import send_chatbot_report_email
from utils.report_pdf import generate_discovery_report_pdf, ReportData


class CollegeSelectorDegreeOptionsView(APIView):
    """Return degree levels and categorized degree type options."""
    permission_classes = []

    def get(self, request):
        return Response({
            'degree_levels': [
                {'value': value, 'label': label}
                for value, label in DEGREE_LEVELS
            ],
            'degree_types': DEGREE_TYPES_BY_LEVEL,
        })


class CollegeSelectorSessionCreateView(APIView):
    """Create a new College Selector session"""
    permission_classes = []

    def post(self, request):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

            # Profile and module completion requirements removed to allow independent module access.
            session = college_selector_service.create_session(user=user)
            serializer = CollegeSelectorSessionSerializer(session)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': f'Failed to create College Selector session: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CollegeSelectorSessionListView(APIView):
    """List College Selector sessions for the user"""
    permission_classes = []

    def get(self, request):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

            is_completed = request.query_params.get('is_completed', None)
            limit = request.query_params.get('limit', None)

            sessions = CollegeSelectorSession.objects.filter(user=user).order_by('-created_at')
            total_count = sessions.count()

            if is_completed is not None:
                is_completed_bool = is_completed.lower() in ['true', '1', 'yes']
                if is_completed_bool:
                    sessions = sessions.filter(current_phase='completed')
                else:
                    sessions = sessions.exclude(current_phase='completed')

            if limit is not None:
                try:
                    sessions = sessions[:int(limit)]
                except ValueError:
                    pass

            serializer = CollegeSelectorSessionBasicSerializer(sessions, many=True)
            return Response({'sessions': serializer.data, 'total_count': total_count})
        except Exception as e:
            return Response(
                {'error': f'Failed to list sessions: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CollegeSelectorSessionDetailView(APIView):
    """Get a College Selector session by ID"""
    permission_classes = []

    def get(self, request, session_id):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

            try:
                session = CollegeSelectorSession.objects.get(session_id=session_id, user=user)
            except CollegeSelectorSession.DoesNotExist:
                return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

            serializer = CollegeSelectorSessionSerializer(session)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': f'Failed to get session: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CollegeSelectorSavePreferencesView(APIView):
    """Save or get static questionnaire preferences for a session"""
    permission_classes = []

    def post(self, request, session_id):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

            session = college_selector_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

            if session.preferences_completed:
                return Response({'error': 'Preferences already saved'}, status=status.HTTP_400_BAD_REQUEST)

            serializer = SavePreferencesRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            session = college_selector_service.save_preferences(session, serializer.validated_data)
            return Response(CollegeSelectorSessionSerializer(session).data)
        except Exception as e:
            return Response(
                {'error': f'Failed to save preferences: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get(self, request, session_id):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

            session = college_selector_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

            return Response({
                'session_id': session.session_id,
                'preferences': session.preferences,
                'preferences_completed': session.preferences_completed,
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to get preferences: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request, session_id):
        """Save partial preferences progress without completing."""
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

            session = college_selector_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

            if session.preferences_completed:
                return Response({'error': 'Preferences already completed'}, status=status.HTTP_400_BAD_REQUEST)

            progress_data = request.data
            current_preferences = session.preferences or {}
            current_preferences.update(progress_data)
            session.preferences = current_preferences
            session.save(update_fields=['preferences', 'updated_at'])

            return Response({
                'session_id': session.session_id,
                'preferences': session.preferences,
                'preferences_completed': session.preferences_completed,
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to save progress: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CollegeSelectorSendMessageView(APIView):
    """Send a message in a College Selector conversation"""
    permission_classes = []

    def post(self, request, session_id):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

            serializer = SendMessageRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            session = college_selector_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

            if not session.preferences_completed:
                return Response(
                    {'error': 'Please complete preferences before starting conversation'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            result = college_selector_service.process_message(session, serializer.validated_data['content'])
            return Response(result)
        except Exception as e:
            return Response(
                {'error': f'Failed to process message: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CollegeMessageStreamView(APIView):
    """
    Server-Sent Events (SSE) view for streaming college selector chatbot responses.
    """
    permission_classes = []

    def get(self, request, session_id):
        """
        Supports streaming responses via GET with content query param.
        """
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

            content = request.query_params.get('content')
            if not content:
                return Response({'error': 'Content is required'}, status=status.HTTP_400_BAD_REQUEST)

            session = college_selector_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

            if not session.preferences_completed:
                return Response(
                    {'error': 'Please complete preferences before starting conversation'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            def sync_stream():
                q = queue.Queue()

                def run_async():
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    async def consume():
                        try:
                            async for chunk in college_selector_service.process_message_stream(session, content):
                                q.put(chunk)
                        except Exception as e:
                            q.put(f"data: {json.dumps({'error': str(e)})}\n\n")
                        finally:
                            q.put(None)
                    
                    loop.run_until_complete(consume())
                    loop.close()

                thread = threading.Thread(target=run_async)
                thread.start()

                while True:
                    chunk = q.get()
                    if chunk is None:
                        break
                    yield chunk

                thread.join()

            response = StreamingHttpResponse(
                sync_stream(),
                content_type='text/event-stream'
            )
            response['Cache-Control'] = 'no-cache'
            return response
        except Exception as e:
            return Response(
                {'error': f'Streaming failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CollegeSelectorMessageHistoryView(APIView):
    """Get message history for a College Selector session"""
    permission_classes = []

    def get(self, request, session_id):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

            session = college_selector_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

            messages = college_selector_service.get_session_messages(session)
            return Response({
                'session_id': session.session_id,
                'messages': messages,
                'current_step': session.current_step,
                'total_steps': session.total_steps,
                'current_phase': session.current_phase,
                'is_active': session.is_active,
                'is_completed': session.is_completed,
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to get message history: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CollegeSelectorSessionEndView(APIView):
    """End a College Selector session"""
    permission_classes = []

    def post(self, request, session_id):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

            session = college_selector_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

            college_selector_service.end_session(session)
            return Response({'message': 'Session ended successfully'})
        except Exception as e:
            return Response(
                {'error': f'Failed to end session: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CollegeSelectorSessionPauseView(APIView):
    """Toggle pause/resume for a College Selector session"""
    permission_classes = []

    def post(self, request, session_id):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

            try:
                session = CollegeSelectorSession.objects.get(session_id=session_id, user=user)
            except CollegeSelectorSession.DoesNotExist:
                return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

            metadata = session.metadata or {}
            pause_events = metadata.get('pause_events', [])
            is_paused = metadata.get('is_paused', False)
            total_paused_seconds = metadata.get('total_paused_seconds', 0)
            now = timezone.now().isoformat()

            if is_paused:
                if pause_events:
                    last_event = pause_events[-1]
                    if last_event.get('paused_at') and not last_event.get('resumed_at'):
                        paused_at = timezone.datetime.fromisoformat(last_event['paused_at'])
                        duration = (timezone.now() - paused_at).total_seconds()
                        last_event['resumed_at'] = now
                        last_event['duration_seconds'] = round(duration)
                        total_paused_seconds += round(duration)
                metadata['is_paused'] = False
                metadata['total_paused_seconds'] = total_paused_seconds
            else:
                pause_events.append({'paused_at': now, 'resumed_at': None, 'duration_seconds': 0})
                metadata['is_paused'] = True

            metadata['pause_events'] = pause_events
            session.metadata = metadata
            session.save(update_fields=['metadata'])

            effective_total = metadata.get('total_paused_seconds', 0)
            if metadata['is_paused'] and pause_events:
                last_event = pause_events[-1]
                if last_event.get('paused_at') and not last_event.get('resumed_at'):
                    paused_at = timezone.datetime.fromisoformat(last_event['paused_at'])
                    effective_total += round((timezone.now() - paused_at).total_seconds())

            return Response({
                'is_paused': metadata['is_paused'],
                'total_paused_seconds': effective_total,
                'pause_events': pause_events,
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to toggle pause: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CollegeSelectorGenerateRecommendationsView(APIView):
    """Generate college recommendations for a session"""
    permission_classes = []

    def post(self, request, session_id):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

            session = college_selector_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

            recommendations = college_selector_service.generate_recommendations(session)
            serializer = CollegeRecommendationSerializer(recommendations, many=True)

            session.refresh_from_db(fields=['token_usage'])

            # Trigger email if not already sent
            if not session.metadata.get('report_emailed'):
                try:
                    transcript = college_selector_service.get_transcript(session)
                    recommendations = college_selector_service.get_recommendations(session)
                    
                    # Generate PDF report
                    pdf_data = ReportData(
                        student_name=user.first_name or "Student",
                        module_name='College Selector',
                        session_id=session.session_id,
                        generated_at=datetime.now().isoformat(),
                        transcript=transcript.get('messages', []),
                        recommendations=recommendations
                    )
                    report_pdf = generate_discovery_report_pdf(pdf_data)

                    send_chatbot_report_email(
                        email=user.email,
                        student_name=user.first_name or "Student",
                        module_name='College Selector',
                        transcript=transcript.get('messages', []),
                        recommendations=serializer.data,
                        session_id=session.session_id,
                        report_pdf=report_pdf
                    )
                    
                    # Mark as emailed
                    session.metadata['report_emailed'] = True
                    session.save(update_fields=['metadata'])
                except Exception as email_err:
                    print(f"Error triggering college chatbot report email: {email_err}")

            return Response({
                'session_id': session.session_id,
                'recommendations': serializer.data,
                'total_count': len(recommendations),
                'token_usage': session.token_usage or {},
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to generate recommendations: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CollegeSelectorGetRecommendationsView(APIView):
    """Get stored college recommendations for a session"""
    permission_classes = []

    def get(self, request, session_id):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

            session = college_selector_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

            recommendations = college_selector_service.get_recommendations(session)
            serializer = CollegeRecommendationSerializer(recommendations, many=True)
            return Response({
                'session_id': session.session_id,
                'recommendations': serializer.data,
                'total_count': len(recommendations),
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to get recommendations: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CollegeSelectorTranscribeAudioView(APIView):
    """Transcribe audio to text using Whisper"""
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = []

    def post(self, request):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

            if 'audio' not in request.FILES:
                return Response({'error': 'No audio file provided'}, status=status.HTTP_400_BAD_REQUEST)

            import os
            whisper_deployment = os.getenv('AZURE_OPENAI_WHISPER_DEPLOYMENT', 'whisper')
            client = create_azure_openai_client()
            transcription = client.audio.transcriptions.create(model=whisper_deployment, file=request.FILES['audio'])
            return Response({'text': transcription.text})
        except Exception as e:
            return Response(
                {'error': f'Transcription failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CollegeSelectorGenerateSpeechView(APIView):
    """Generate speech from text using TTS"""
    permission_classes = []

    def post(self, request):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

            serializer = GenerateSpeechRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            import os
            tts_deployment = os.getenv('AZURE_OPENAI_TTS_DEPLOYMENT', 'tts')
            client = create_azure_openai_client()
            response = client.audio.speech.create(
                model=tts_deployment,
                voice=serializer.validated_data.get('voice', 'nova'),
                input=serializer.validated_data['text'],
            )

            audio_content = response.content
            http_response = HttpResponse(audio_content, content_type='audio/mpeg')
            http_response['Content-Disposition'] = 'attachment; filename="speech.mp3"'
            return http_response
        except Exception as e:
            return Response(
                {'error': f'Speech generation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CollegeSelectorTranscriptView(APIView):
    """Get conversation transcript"""
    permission_classes = []

    def get(self, request, session_id):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

            session = college_selector_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

            transcript = college_selector_service.get_transcript(session)
            return Response(transcript)
        except Exception as e:
            return Response(
                {'error': f'Failed to get transcript: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CollegeSelectorTestScoresView(APIView):
    """Update standardized test scores (stored in the user's profile)."""
    permission_classes = []

    def put(self, request):
        """Replace the user's standardized test scores and persist to profile."""
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

            new_scores = request.data.get("test_scores")
            if not isinstance(new_scores, list):
                return Response(
                    {"error": "'test_scores' must be an array."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            from apps.profiles.models import UserProfile
            import copy
            import json

            user_id = user.id
            obj, created = UserProfile.objects.get_or_create(user_id=user_id)
            profile_data = copy.deepcopy(obj.profile_json) if obj.profile_json else {}

            print(f"[TestScores PUT] user_id={user_id}, created={created}")
            print(f"[TestScores PUT] BEFORE top-level keys: {list(profile_data.keys()) if isinstance(profile_data, dict) else type(profile_data)}")

            # Navigate into the profile blob
            has_profile_key = "profile" in profile_data
            inner = profile_data.get("profile", profile_data) if has_profile_key else profile_data
            if not isinstance(inner, dict):
                inner = {}
                if has_profile_key:
                    profile_data["profile"] = inner
                else:
                    profile_data = inner

            print(f"[TestScores PUT] has_profile_key={has_profile_key}, inner keys: {list(inner.keys()) if isinstance(inner, dict) else type(inner)}")

            educational = inner.get("educational", {})
            if not isinstance(educational, dict):
                educational = {}

            print(f"[TestScores PUT] educational keys BEFORE: {list(educational.keys())}")

            # Always save at top-level educational.testScores (matching how
            # the profile edit page stores them).  Also clear any nested
            # duplicates inside section objects so stale copies don't persist.
            educational["testScores"] = new_scores
            for key in ("highSchool", "undergraduate", "postgraduate", "tenPlus"):
                section = educational.get(key)
                if isinstance(section, dict) and "testScores" in section:
                    print(f"[TestScores PUT] Clearing nested testScores from {key}")
                    del section["testScores"]

            inner["educational"] = educational
            if has_profile_key:
                profile_data["profile"] = inner

            obj.profile_json = profile_data
            obj.save()

            # Verify the save by re-reading
            obj.refresh_from_db()
            verify_inner = obj.profile_json.get("profile", obj.profile_json) if isinstance(obj.profile_json, dict) else {}
            verify_edu = verify_inner.get("educational", {}) if isinstance(verify_inner, dict) else {}
            verify_scores = verify_edu.get("testScores", []) if isinstance(verify_edu, dict) else []
            print(f"[TestScores PUT] VERIFY after save: user_id={user_id}, testScores count={len(verify_scores)}, scores={json.dumps(verify_scores[:1]) if verify_scores else '[]'}")

            return Response({"test_scores": new_scores, "message": "Test scores updated successfully."})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {"error": f"Failed to update test scores: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CollegeSelectorSessionDebugView(APIView):
    """Get debug information for a College Selector session"""
    permission_classes = []

    @extend_schema(
        summary="Get Session Debug Info",
        description="Returns debug information including system prompts, model info, and user context for a College Selector session.",
        responses={
            200: OpenApiResponse(description="Debug information"),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Session not found"),
            500: OpenApiResponse(description="Server error"),
        }
    )
    def get(self, request, session_id):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            try:
                session = CollegeSelectorSession.objects.get(session_id=session_id)
            except CollegeSelectorSession.DoesNotExist:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Verify ownership
            if session.user_id != user.id:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            from .langchain_service import college_selector_langchain_service
            from .prompts import (
                CONVERSATION_SYSTEM_PROMPT,
                RECOMMENDATIONS_SYSTEM_PROMPT,
                build_preferences_context,
            )
            from utils.azure_openai import get_azure_openai_config
            from utils.profile_formatting import format_user_profile_context

            # Model info
            try:
                config = get_azure_openai_config()
                deployment = config.get('azure_deployment', 'unknown')
            except Exception:
                deployment = 'unknown'

            main_llm_info = {
                'type': 'AzureChatOpenAI',
                'model': deployment,
                'temperature': 0.7,
                'max_tokens': 800,
            }
            recommendations_llm_info = {
                'type': 'AzureChatOpenAI',
                'model': deployment,
                'temperature': 0.7,
                'max_tokens': 16000,
            }

            # User context
            user_profile = get_user_profile_data(user)
            profile_context = format_user_profile_context(user_profile or {})

            # Preferences context
            preferences_context = build_preferences_context(session.preferences or {})

            # Build system prompt as it would be used
            conversation_prompt = CONVERSATION_SYSTEM_PROMPT.format(
                preferences_context=preferences_context,
                profile_context=profile_context,
            )

            # Session state
            bot_messages = session.messages.filter(type='bot').count()
            user_messages = session.messages.filter(type='user').count()

            debug_info = {
                'session_id': session.session_id,
                'current_phase': session.current_phase,
                'model_info': {
                    'provider': 'Azure OpenAI',
                    'main_llm': main_llm_info,
                    'recommendations_llm': recommendations_llm_info,
                },
                'system_prompts': {
                    'conversation_prompt': conversation_prompt,
                    'recommendations_prompt': RECOMMENDATIONS_SYSTEM_PROMPT,
                },
                'preferences_context': preferences_context,
                'user_context': profile_context,
                'session_state': {
                    'current_step': session.current_step,
                    'total_steps': session.total_steps,
                    'bot_messages': bot_messages,
                    'user_messages': user_messages,
                    'preferences_completed': session.preferences_completed,
                },
                'token_usage': session.token_usage or {},
            }

            return Response(debug_info, status=status.HTTP_200_OK)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Failed to get debug info: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CollegeSelectorHealthCheckView(APIView):
    """Health check endpoint"""
    permission_classes = []

    def get(self, request):
        return Response({'status': 'healthy', 'service': 'college_selector'})
