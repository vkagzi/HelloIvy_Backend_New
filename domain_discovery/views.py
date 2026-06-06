"""
Stream & Subject Selection API Views
Provides REST API endpoints for Stream & Subject Selection conversations using LangChain + Azure OpenAI
"""
import jwt
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from datetime import datetime
from django.http import HttpResponse, StreamingHttpResponse
from drf_spectacular.utils import extend_schema, OpenApiResponse
import threading
import queue

from apps.accounts.models import User
from utils.jwt import JWT_SECRET_KEY, ALGORITHM
from .models import DomainSession, DomainMessage, DomainRecommendation
from .serializers import (
    DomainSessionSerializer,
    DomainSessionBasicSerializer,
    DomainMessageSerializer,
    DomainRecommendationSerializer,
    SendMessageRequestSerializer,
    SendMessageResponseSerializer,
    GenerateRecommendationsRequestSerializer,
    TranscribeAudioRequestSerializer,
    TranscribeAudioResponseSerializer,
    GenerateSpeechRequestSerializer,
    ResultsSummarySerializer,
    TranscriptSerializer,
)
from .services import domain_discovery_service
from apps.profiles.services import calculate_profile_completion
from utils.profile_helpers import get_user_profile_data
from utils.user_helpers import get_user_instance, get_user_display_name
from utils.azure_openai import create_azure_openai_client
from django.utils import timezone
from utils.email import send_chatbot_report_email
from utils.report_pdf import generate_discovery_report_pdf, ReportData


def get_user_from_token_param(request):
    """
    Get user from query parameter token (for file downloads opened in browser).
    Falls back to request.user authentication.
    """
    # First try the standard request.user authentication
    user = get_user_instance(request.user)
    if user:
        return user
    
    # Fallback: check for token in query params (for browser file downloads)
    token = request.query_params.get('token')
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
            return User.objects.get(email=payload["email"], token=payload["token"])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, User.DoesNotExist, KeyError):
            return None
    
    return None


class DomainSessionCreateView(APIView):
    """Create a new Stream & Subject Selection session"""
    permission_classes = []  # Allow authenticated users

    @extend_schema(
        summary="Create Stream & Subject Selection Session",
        description="Creates a new Stream & Subject Selection session and returns the initial question.",
        responses={
            201: DomainSessionSerializer,
            401: OpenApiResponse(description="Authentication required"),
            500: OpenApiResponse(description="Server error"),
        }
    )
    def post(self, request):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Create a new session
            session = domain_discovery_service.create_session(user=user)
            serializer = DomainSessionSerializer(session)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': f'Failed to create Stream & Subject Selection session: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DomainSessionListView(APIView):
    """List all Stream & Subject Selection sessions for the user"""
    permission_classes = []

    @extend_schema(
        summary="List Stream & Subject Selection Sessions",
        description="Returns all Stream & Subject Selection sessions for the authenticated user. Supports filtering by is_completed and limiting results.",
        responses={
            200: DomainSessionBasicSerializer(many=True),
            401: OpenApiResponse(description="Authentication required"),
        }
    )
    def get(self, request):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Get query parameters for filtering
            is_completed = request.query_params.get('is_completed', None)
            # Legacy support: treat is_active=false as is_completed=true
            is_active_param = request.query_params.get('is_active', None)
            limit = request.query_params.get('limit', None)
            
            # Start with base queryset
            sessions = DomainSession.objects.filter(user=user).order_by('-created_at')
            
            # Get total count before filtering
            total_count = sessions.count()
            
            # Apply is_completed filter if provided
            if is_completed is not None:
                is_completed_bool = is_completed.lower() in ['true', '1', 'yes']
                if is_completed_bool:
                    # Completed: current_step >= total_steps
                    from django.db.models import F
                    sessions = sessions.filter(current_step__gte=F('total_steps'))
                else:
                    from django.db.models import F
                    sessions = sessions.filter(current_step__lt=F('total_steps'))
            elif is_active_param is not None:
                # Legacy support: is_active=false meant "completed" 
                is_active_bool = is_active_param.lower() in ['true', '1', 'yes']
                if not is_active_bool:
                    # is_active=false => completed sessions
                    from django.db.models import F
                    sessions = sessions.filter(current_step__gte=F('total_steps'))
                else:
                    # is_active=true => non-completed sessions
                    from django.db.models import F
                    sessions = sessions.filter(current_step__lt=F('total_steps'))
            
            # Apply limit if provided
            if limit is not None:
                try:
                    limit_int = int(limit)
                    sessions = sessions[:limit_int]
                except ValueError:
                    pass  # Ignore invalid limit values
            
            serializer = DomainSessionBasicSerializer(sessions, many=True)
            return Response({
                'sessions': serializer.data,
                'total_count': total_count
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to list sessions: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Backward-compatible alias
DomainSessionCurrentView = None  # Removed — use DomainSessionDetailView


class DomainSessionDetailView(APIView):
    """Get a Stream & Subject Selection session by ID"""
    permission_classes = []

    @extend_schema(
        summary="Get Stream & Subject Selection Session by ID",
        description="Returns the Stream & Subject Selection session with the given session_id.",
        responses={
            200: DomainSessionSerializer,
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Session not found"),
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
                session = DomainSession.objects.get(session_id=session_id, user=user)
            except DomainSession.DoesNotExist:
                return Response(
                    {'error': 'Stream & Subject Selection session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = DomainSessionSerializer(session)
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {'error': f'Failed to get session: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DomainMessageCreateView(APIView):
    """Send a message in a Stream & Subject Selection conversation"""
    permission_classes = []

    @extend_schema(
        summary="Send Message in Stream & Subject Selection",
        description="Sends a user message and receives the AI response.",
        request=SendMessageRequestSerializer,
        responses={
            200: SendMessageResponseSerializer,
            400: OpenApiResponse(description="Invalid request"),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Session not found"),
            500: OpenApiResponse(description="Server error"),
        }
    )
    def post(self, request, session_id):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            serializer = SendMessageRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            content = serializer.validated_data['content']

            session = domain_discovery_service.get_session_by_id(session_id)
            if not session:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Verify session belongs to user
            if not session.user or session.user.id != user.id:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            result = domain_discovery_service.process_message(session, content)
            return Response(result)

        except Exception as e:
            return Response(
                {'error': f'Failed to process message: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DomainMessageStreamView(APIView):
    """Streaming version of message creation using SSE"""
    permission_classes = []

    @extend_schema(
        summary="Stream Message in Stream & Subject Selection",
        description="Sends a user message and receives the AI response as a stream of Server-Sent Events (SSE).",
        request=SendMessageRequestSerializer,
        responses={
            200: OpenApiResponse(description="Stream of SSE events"),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Session not found"),
        }
    )
    def post(self, request, session_id):
        try:
            user = get_user_instance(request.user)
            if not user:
                return HttpResponse(
                    json.dumps({'error': 'Authentication required'}),
                    status=401,
                    content_type='application/json'
                )

            content = request.data.get('content')
            if not content:
                return HttpResponse(
                    json.dumps({'error': 'Content is required'}),
                    status=400,
                    content_type='application/json'
                )

            session = domain_discovery_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return HttpResponse(
                    json.dumps({'error': 'Session not found'}),
                    status=404,
                    content_type='application/json'
                )

            def sync_stream():
                q = queue.Queue()

                def run_async():
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    async def consume():
                        try:
                            async for chunk in domain_discovery_service.process_message_stream(session, content):
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
            response['X-Accel-Buffering'] = 'no'  # Disable buffering for Nginx
            return response

        except Exception as e:
            return HttpResponse(
                json.dumps({'error': f'Failed to start stream: {str(e)}'}),
                status=500,
                content_type='application/json'
            )


class DomainMessageHistoryView(APIView):
    """Get message history for a Stream & Subject Selection session"""
    permission_classes = []

    @extend_schema(
        summary="Get Stream & Subject Selection Message History",
        description="Returns all messages for a specific session.",
        responses={
            200: DomainMessageSerializer(many=True),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Session not found"),
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

            session = domain_discovery_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            messages = domain_discovery_service.get_session_messages(session)
            
            return Response({
                'session_id': session.session_id,
                'messages': messages,
                'current_step': session.current_step,
                'total_steps': session.total_steps,
                # RIASEC fields commented out - may be re-enabled later
                # 'riasec_completed': session.riasec_completed,
                'deepdive_completed': session.deepdive_completed,
                'current_phase': session.current_phase,
                'is_active': session.is_active,
                'is_completed': session.is_completed
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to get message history: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DomainSessionEndView(APIView):
    """End a Stream & Subject Selection session"""
    permission_classes = []

    @extend_schema(
        summary="End Stream & Subject Selection Session",
        description="Ends the specified Stream & Subject Selection session.",
        responses={
            200: OpenApiResponse(description="Session ended successfully"),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Session not found"),
        }
    )
    def post(self, request, session_id):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            session = domain_discovery_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            domain_discovery_service.end_session(session)
            return Response({'message': 'Session ended successfully'})

        except Exception as e:
            return Response(
                {'error': f'Failed to end session: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DomainSessionPauseView(APIView):
    """Toggle pause/resume for a Stream & Subject Selection session"""
    permission_classes = []

    @extend_schema(
        summary="Toggle Pause/Resume Stream & Subject Selection Session",
        description="Pauses or resumes the session timer. Stores pause/resume events in session metadata.",
        responses={
            200: OpenApiResponse(description="Pause state toggled"),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Session not found"),
        }
    )
    def post(self, request, session_id):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            try:
                session = DomainSession.objects.get(session_id=session_id, user=user)
            except DomainSession.DoesNotExist:
                return Response(
                    {'error': 'Stream & Subject Selection session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            metadata = session.metadata or {}
            pause_events = metadata.get('pause_events', [])
            is_paused = metadata.get('is_paused', False)
            total_paused_seconds = metadata.get('total_paused_seconds', 0)
            now = timezone.now().isoformat()

            if is_paused:
                # Resume: calculate paused duration and add to total
                if pause_events:
                    last_event = pause_events[-1]
                    if last_event.get('paused_at') and not last_event.get('resumed_at'):
                        paused_at = timezone.datetime.fromisoformat(last_event['paused_at'])
                        resumed_at = timezone.now()
                        duration = (resumed_at - paused_at).total_seconds()
                        last_event['resumed_at'] = now
                        last_event['duration_seconds'] = round(duration)
                        total_paused_seconds += round(duration)

                metadata['is_paused'] = False
                metadata['total_paused_seconds'] = total_paused_seconds
            else:
                # Pause: record pause start
                pause_events.append({
                    'paused_at': now,
                    'resumed_at': None,
                    'duration_seconds': 0,
                })
                metadata['is_paused'] = True

            metadata['pause_events'] = pause_events
            session.metadata = metadata
            session.save(update_fields=['metadata'])

            # Calculate effective total including any ongoing pause
            effective_total = metadata.get('total_paused_seconds', 0)
            if metadata['is_paused'] and pause_events:
                last_event = pause_events[-1]
                if last_event.get('paused_at') and not last_event.get('resumed_at'):
                    paused_at = timezone.datetime.fromisoformat(last_event['paused_at'])
                    ongoing = (timezone.now() - paused_at).total_seconds()
                    effective_total += round(ongoing)

            return Response({
                'is_paused': metadata['is_paused'],
                'total_paused_seconds': effective_total,
                'pause_events': pause_events,
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to toggle pause: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DomainRecommendationsGenerateView(APIView):
    """Generate domain recommendations for a session"""
    permission_classes = []

    @extend_schema(
        summary="Generate Domain Recommendations",
        description="Generates personalized domain recommendations based on the conversation.",
        responses={
            200: DomainRecommendationSerializer(many=True),
            400: OpenApiResponse(description="Invalid request"),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Session not found"),
            500: OpenApiResponse(description="Server error"),
        }
    )
    def post(self, request, session_id):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            session = domain_discovery_service.get_session_by_id(session_id)
            
            if not session or not session.user or session.user.id != user.id:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            recommendations = domain_discovery_service.generate_recommendations(session)
            serializer = DomainRecommendationSerializer(recommendations, many=True)
            
            # Refresh session to get latest token usage
            session.refresh_from_db(fields=['token_usage'])
            
            return Response({
                'session_id': session.session_id,
                'recommendations': serializer.data,
                'total_count': len(recommendations),
                'token_usage': session.token_usage or {}
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to generate recommendations: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DomainRecommendationsGetView(APIView):
    """Get stored domain recommendations for a session"""
    permission_classes = []

    @extend_schema(
        summary="Get Domain Recommendations",
        description="Returns stored domain recommendations for a session.",
        responses={
            200: DomainRecommendationSerializer(many=True),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Session not found"),
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

            session = domain_discovery_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            recommendations = domain_discovery_service.get_recommendations(session)
            serializer = DomainRecommendationSerializer(recommendations, many=True)
            
            return Response({
                'session_id': session.session_id,
                'recommendations': serializer.data,
                'total_count': len(recommendations)
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to get recommendations: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DomainTranscribeAudioView(APIView):
    """Transcribe audio to text using Whisper"""
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = []

    @extend_schema(
        summary="Transcribe Audio for Stream & Subject Selection",
        description="Transcribes audio to text using Azure OpenAI Whisper.",
        request=TranscribeAudioRequestSerializer,
        responses={
            200: TranscribeAudioResponseSerializer,
            400: OpenApiResponse(description="No audio file provided"),
            401: OpenApiResponse(description="Authentication required"),
            500: OpenApiResponse(description="Transcription failed"),
        }
    )
    def post(self, request):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            if 'audio' not in request.FILES:
                return Response(
                    {'error': 'No audio file provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            audio_file = request.FILES['audio']
            
            import os

            whisper_deployment = os.getenv('AZURE_OPENAI_WHISPER_DEPLOYMENT', 'whisper')
            client = create_azure_openai_client()
            
            transcription = client.audio.transcriptions.create(
                model=whisper_deployment,
                file=audio_file
            )
            
            return Response({'text': transcription.text})

        except Exception as e:
            return Response(
                {'error': f'Transcription failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DomainGenerateSpeechView(APIView):
    """Generate speech from text using TTS"""
    permission_classes = []

    @extend_schema(
        summary="Generate Speech for Stream & Subject Selection",
        description="Generates speech from text using Azure OpenAI TTS.",
        request=GenerateSpeechRequestSerializer,
        responses={
            200: OpenApiResponse(description="Audio file"),
            400: OpenApiResponse(description="Invalid request"),
            401: OpenApiResponse(description="Authentication required"),
            500: OpenApiResponse(description="TTS failed"),
        }
    )
    def post(self, request):
        try:
            user = get_user_instance(request.user)
            if not user:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            serializer = GenerateSpeechRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            text = serializer.validated_data['text']
            voice = serializer.validated_data.get('voice', 'nova')
            
            import os

            tts_deployment = os.getenv('AZURE_OPENAI_TTS_DEPLOYMENT', 'tts')
            client = create_azure_openai_client(use_tts_endpoint=True)
            
            response = client.audio.speech.create(
                model=tts_deployment,
                voice=voice,
                input=text
            )
            
            audio_content = response.content
            
            http_response = HttpResponse(audio_content, content_type='audio/mpeg')
            http_response['Content-Disposition'] = 'attachment; filename="speech.mp3"'
            return http_response

        except Exception as e:
            return Response(
                {'error': f'TTS failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DomainReportGenerateView(APIView):
    """Generate and return the final Stream & Subject Selection report"""
    permission_classes = []

    @extend_schema(
        summary="Generate Final Stream & Subject Selection Report",
        description="Generates the final comprehensive report including snapshot, interests, strengths, and domain recommendations.",
        responses={
            200: OpenApiResponse(description="Report generated successfully"),
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

            session = domain_discovery_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Generate final report
            report = domain_discovery_service.generate_final_report(session)
            
            # Trigger email if not already sent
            if not session.metadata.get('report_emailed'):
                try:
                    transcript = domain_discovery_service.get_conversation_transcript(session)
                    recommendations = domain_discovery_service.get_recommendations(session)
                    from .serializers import DomainRecommendationSerializer
                    rec_data = DomainRecommendationSerializer(recommendations, many=True).data
                    
                    # Generate PDF report
                    pdf_data = ReportData(
                        student_name=report.get('student_name', 'Student'),
                        module_name='Stream & Subject Selection',
                        session_id=session.session_id,
                        generated_at=report.get('generated_at', datetime.now().isoformat()),
                        transcript=transcript.get('messages', []),
                        recommendations=rec_data
                    )
                    report_pdf = generate_discovery_report_pdf(pdf_data)

                    send_chatbot_report_email(
                        email=user.email,
                        student_name=report.get('student_name', 'Student'),
                        module_name='Stream & Subject Selection',
                        transcript=transcript.get('messages', []),
                        recommendations=rec_data,
                        session_id=session.session_id,
                        report_pdf=report_pdf
                    )
                    
                    # Mark as emailed
                    session.metadata['report_emailed'] = True
                    session.save(update_fields=['metadata'])
                except Exception as email_err:
                    print(f"Error triggering chatbot report email: {email_err}")

            return Response({
                'session_id': session.session_id,
                'report': report.get('report_json', {}),
                'student_name': report.get('student_name', 'Student'),
                'generated_at': report.get('generated_at')
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to generate report: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DomainReportDownloadView(APIView):
    """Download the Stream & Subject Selection report as HTML"""
    permission_classes = []
    authentication_classes = []  # Allow token via query param for browser downloads

    @extend_schema(
        summary="Download Stream & Subject Selection Report",
        description="Downloads the final report as an HTML file. Supports token auth via query param for browser downloads.",
        responses={
            200: OpenApiResponse(description="HTML report file"),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Session not found"),
            500: OpenApiResponse(description="Server error"),
        }
    )
    def get(self, request, session_id):
        try:
            # Support both header auth and query param token for file downloads
            user = get_user_from_token_param(request)
            if not user:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            session = domain_discovery_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Generate final report
            report = domain_discovery_service.generate_final_report(session)
            html_content = report.get('report_html', '<p>Report not available</p>')
            
            # Return as HTML file download
            http_response = HttpResponse(html_content, content_type='text/html')
            student_name = report.get('student_name', 'Student').replace(' ', '_')
            http_response['Content-Disposition'] = f'attachment; filename="Domain_Discovery_Report_{student_name}.html"'
            return http_response

        except Exception as e:
            return Response(
                {'error': f'Failed to download report: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DomainResultsSummaryView(APIView):
    """Get results summary after conversation completion"""
    permission_classes = []

    @extend_schema(
        summary="Get Results Summary",
        description="Returns summary of results including interests, strengths, and domain recommendations.",
        responses={
            200: ResultsSummarySerializer,
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

            # Optimized query with prefetch_related to avoid N+1 queries
            from django.db.models import Prefetch
            session = domain_discovery_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get results summary (with caching)
            results = domain_discovery_service.get_results_summary(session)
            
            return Response({
                'session_id': results.get('session_id'),
                'student_name': results.get('student_name'),
                'current_step': results.get('current_step'),
                'total_steps': results.get('total_steps'),
                'completion_percentage': results.get('completion_percentage'),
                'interests_identified': results.get('interests_identified', []),
                'strengths_identified': results.get('strengths_identified', []),
                # RIASEC fields commented out - may be re-enabled later
                # 'riasec_scores': results.get('riasec_scores', {}),
                # 'top_dimensions': results.get('top_dimensions', []),
                'primary_domains': results.get('primary_domains', []),
                'secondary_domains': results.get('secondary_domains', [])
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to get results summary: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DomainTranscriptView(APIView):
    """Get conversation transcript"""
    permission_classes = []

    @extend_schema(
        summary="Get Conversation Transcript",
        description="Returns formatted transcript of the conversation with all questions and responses.",
        responses={
            200: TranscriptSerializer,
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

            session = domain_discovery_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get transcript
            transcript = domain_discovery_service.get_conversation_transcript(session)
            
            return Response(transcript)

        except Exception as e:
            return Response(
                {'error': f'Failed to get transcript: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DomainTranscriptDownloadView(APIView):
    """Download conversation transcript as text file"""
    permission_classes = []
    authentication_classes = []  # Allow token via query param for browser downloads

    @extend_schema(
        summary="Download Conversation Transcript",
        description="Downloads the conversation transcript as a text file. Supports token auth via query param for browser downloads.",
        responses={
            200: OpenApiResponse(description="Text file download"),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Session not found"),
            500: OpenApiResponse(description="Server error"),
        }
    )
    def get(self, request, session_id):
        try:
            # Support both header auth and query param token for file downloads
            user = get_user_from_token_param(request)
            if not user:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            session = domain_discovery_service.get_session_by_id(session_id)
            if not session:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check session ownership (handle case where session.user might be None)
            if not session.user or session.user.id != user.id:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Generate transcript text
            transcript_text = domain_discovery_service.generate_transcript_file(session)
            
            # Return as text file download
            http_response = HttpResponse(transcript_text, content_type='text/plain')
            student_name = get_user_display_name(None, session.user, 'Student')
            http_response['Content-Disposition'] = f'attachment; filename="Domain_Discovery_Transcript_{student_name}.txt"'
            return http_response

        except Exception as e:
            return Response(
                {'error': f'Failed to download transcript: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DomainHealthCheckView(APIView):
    """Health check endpoint for Stream & Subject Selection service"""
    
    @extend_schema(
        summary="Stream & Subject Selection Health Check",
        description="Returns the health status of the Stream & Subject Selection service.",
        responses={
            200: OpenApiResponse(description="Service is healthy"),
        }
    )
    def get(self, request):
        return Response({
            'status': 'healthy',
            'service': 'domain-discovery',
            'message': 'Stream & Subject Selection service is running'
        })


class DomainDebugInfoView(APIView):
    """Debug endpoint to get system prompt, model info, and user profile context"""
    permission_classes = []

    @extend_schema(
        summary="Get Debug Information",
        description="Returns debugging information including system prompt, model details, and user profile context.",
        responses={
            200: OpenApiResponse(description="Debug information"),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Session not found"),
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

            session = domain_discovery_service.get_session_by_id(session_id)
            if not session or not session.user or session.user.id != user.id:
                return Response(
                    {'error': 'Session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get debug info from service
            debug_info = domain_discovery_service.get_debug_info(session)
            
            return Response(debug_info)

        except Exception as e:
            return Response(
                {'error': f'Failed to get debug info: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SubmitModuleReviewView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        print("GET HIT")
        return Response({"message": "GET OK"})

    def post(self, request):
        user = get_user_instance(request.user)
        if not user:
            return Response(
                {"error": "Authentication required"},
                status=401
            )

        rating = request.data.get("rating")
        comment = request.data.get("comment")
        module = request.data.get("module")

        if not rating or not module:
            return Response(
                {"error": "rating and module required"},
                status=400
            )

        ModuleReview.objects.create(
            user=user,
            rating=rating,
            comment=comment,
            module=module
        )

        return Response(
            {"message": "Review saved successfully"}
        )