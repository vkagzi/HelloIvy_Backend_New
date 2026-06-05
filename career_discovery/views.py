"""
Career & Degree Selection API Views
Provides REST API endpoints for Career & Degree Selection conversations using LangChain + Azure OpenAI
"""
from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.accounts.models import User
from .models import CareerSession, CareerMessage, CareerRecommendation
from domain_discovery.models import DomainSession
from domain_discovery.constants import DOMAIN_CONFIG
from .serializers import (
    CareerSessionSerializer,
    CareerSessionBasicSerializer,
    CareerMessageSerializer,
    CareerRecommendationSerializer,
    SendMessageRequestSerializer,
    SendMessageResponseSerializer,
    GenerateRecommendationsRequestSerializer,
)
from .services import career_discovery_service
from utils.user_helpers import get_user_instance
from utils.profile_helpers import get_user_profile_data
from utils.profile_formatting import format_user_profile_context
from django.utils import timezone


class CareerDomainsListView(APIView):
    """List all predefined domains available for career discovery"""
    permission_classes = []

    @extend_schema(
        summary="List Available Domains",
        description="Returns all predefined domains with descriptions that users can choose from.",
        responses={200: OpenApiResponse(description="List of domains")},
    )
    def get(self, request):
        domains = [
            {
                'name': str(domain),
                'description': description,
            }
            for domain, description in DOMAIN_CONFIG.items()
        ]
        return Response({'domains': domains})


class CareerSessionCreateView(APIView):
    """Create a new Career & Degree Selection session"""
    permission_classes = []  # Allow authenticated users

    @extend_schema(
        summary="Create Career & Degree Selection Session",
        description=(
            "Creates a new Career & Degree Selection session and returns the initial question. "
            "Requires primary_domain (and optionally secondary_domain) for domain choices. "
            "domain_session_id is optional — if provided, the session will be linked to a prior "
            "Stream & Subject Selection session for richer context."
        ),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'primary_domain': {
                        'type': 'string',
                        'description': 'The primary domain the user selected'
                    },
                    'secondary_domain': {
                        'type': 'string',
                        'description': 'The secondary domain the user selected (optional)'
                    },
                    'domain_session_id': {
                        'type': 'string',
                        'description': 'Optional domain session ID to link with this career session'
                    },
                },
                'required': ['primary_domain']
            }
        },
        responses={
            201: CareerSessionSerializer,
            400: OpenApiResponse(description="Invalid request"),
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

            # Get domain choices from request body
            primary_domain = request.data.get('primary_domain')
            secondary_domain = request.data.get('secondary_domain')

            if not primary_domain:
                return Response(
                    {
                        'error': 'Primary domain required',
                        'message': 'Please provide primary_domain to start a career session.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate domain names against predefined list
            valid_domains = {str(d) for d in DOMAIN_CONFIG.keys()}
            if primary_domain not in valid_domains:
                return Response(
                    {
                        'error': 'Invalid primary domain',
                        'message': f'The domain "{primary_domain}" is not a valid domain.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            if secondary_domain and secondary_domain not in valid_domains:
                return Response(
                    {
                        'error': 'Invalid secondary domain',
                        'message': f'The domain "{secondary_domain}" is not a valid domain.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Optionally link to a domain discovery session
            domain_session = None
            domain_session_id = request.data.get('domain_session_id')
            if domain_session_id:
                try:
                    domain_session = DomainSession.objects.get(
                        session_id=domain_session_id,
                        user=user
                    )
                except DomainSession.DoesNotExist:
                    pass  # Proceed without linking — domain session is optional

            # Create career session with domain choices
            session = career_discovery_service.create_session(
                user=user,
                domain_session=domain_session,
                primary_domain=primary_domain,
                secondary_domain=secondary_domain,
            )
            serializer = CareerSessionSerializer(session)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': f'Failed to create Career & Degree Selection session: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CareerSessionListView(APIView):
    """List all Career & Degree Selection sessions for the user"""
    permission_classes = []

    @extend_schema(
        summary="List Career & Degree Selection Sessions",
        description="Returns all Career & Degree Selection sessions for the authenticated user.",
        responses={
            200: CareerSessionBasicSerializer(many=True),
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

            sessions = CareerSession.objects.filter(user=user).order_by('-created_at')
            serializer = CareerSessionBasicSerializer(sessions, many=True)
            return Response({
                'sessions': serializer.data,
                'total_count': sessions.count()
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to list sessions: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Backward-compatible alias
CareerSessionCurrentView = None  # Removed — use CareerSessionDetailView


class CareerSessionDetailView(APIView):
    """Get a Career & Degree Selection session by ID"""
    permission_classes = []

    @extend_schema(
        summary="Get Session by ID",
        description="Returns the Career & Degree Selection session with the given session_id.",
        responses={
            200: CareerSessionSerializer,
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
                session = CareerSession.objects.get(session_id=session_id, user=user)
            except CareerSession.DoesNotExist:
                return Response(
                    {'error': 'Career & Degree Selection session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = CareerSessionSerializer(session)
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {'error': f'Failed to get session: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CareerMessageCreateView(APIView):
    """Send a message in the Career & Degree Selection conversation"""
    permission_classes = []

    @extend_schema(
        summary="Send Message",
        description="Send a user message and receive the next AI-generated question.",
        request=SendMessageRequestSerializer,
        responses={
            200: SendMessageResponseSerializer,
            400: OpenApiResponse(description="Invalid request"),
            404: OpenApiResponse(description="Session not found"),
        }
    )
    def post(self, request, session_id):
        try:
            serializer = SendMessageRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {'error': 'content is required', 'details': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            content = serializer.validated_data['content']

            # Get the session
            session = career_discovery_service.get_session_by_id(session_id)
            if not session:
                return Response(
                    {'error': 'Career & Degree Selection session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check if session is completed
            if session.is_completed:
                return Response(
                    {'error': 'This session has been completed. Please start a new session.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Process the message
            result = career_discovery_service.process_message(session, content)
            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'Failed to process message: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CareerMessageStreamView(APIView):
    """Streaming version of message creation"""
    permission_classes = []

    def post(self, request, session_id):
        try:
            content = request.data.get('content')
            if not content:
                return Response(
                    {'error': 'content is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            session = career_discovery_service.get_session_by_id(session_id)
            if not session:
                return Response(
                    {'error': 'Career & Degree Selection session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            if session.is_completed:
                return Response(
                    {'error': 'This session has been completed.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            def sync_stream():
                import asyncio
                loop = asyncio.new_event_loop()
                agen = career_discovery_service.process_message_stream(session, content)
                try:
                    while True:
                        try:
                            chunk = loop.run_until_complete(agen.__anext__())
                            yield chunk
                        except StopAsyncIteration:
                            break
                finally:
                    loop.close()

            return StreamingHttpResponse(
                sync_stream(),
                content_type='text/event-stream'
            )

        except Exception as e:
            return Response(
                {'error': f'Failed to process message: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CareerMessageHistoryView(APIView):
    """Get conversation history for a session"""
    permission_classes = []

    @extend_schema(
        summary="Get Message History",
        description="Returns all messages for a Career & Degree Selection session.",
        responses={
            200: CareerMessageSerializer(many=True),
            404: OpenApiResponse(description="Session not found"),
        }
    )
    def get(self, request, session_id):
        try:
            session = career_discovery_service.get_session_by_id(session_id)
            if not session:
                return Response(
                    {'error': 'Career & Degree Selection session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            messages = career_discovery_service.get_session_messages(session)

            return Response({
                'session_id': session_id,
                'messages': messages,
                'current_step': session.current_step,
                'total_steps': session.total_steps,
                'total_questions': session.total_steps,  # Same as total_steps (total number of questions to ask)
                'current_phase': session.current_phase,
                'is_active': session.is_active,
                'is_completed': session.is_completed
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to get conversation history: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CareerSessionEndView(APIView):
    """End a Career & Degree Selection session"""
    permission_classes = []

    @extend_schema(
        summary="End Session",
        description="Ends an active Career & Degree Selection session.",
        responses={
            200: OpenApiResponse(description="Session ended successfully"),
            404: OpenApiResponse(description="Session not found"),
        }
    )
    def post(self, request, session_id):
        try:
            session = career_discovery_service.get_session_by_id(session_id)
            if not session:
                return Response(
                    {'error': 'Career & Degree Selection session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            career_discovery_service.end_session(session)
            return Response({'message': 'Career & Degree Selection session ended successfully'})

        except Exception as e:
            return Response(
                {'error': f'Failed to end session: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CareerSessionPauseView(APIView):
    """Toggle pause/resume for a Career & Degree Selection session"""
    permission_classes = []

    @extend_schema(
        summary="Toggle Pause/Resume Career & Degree Selection Session",
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
                session = CareerSession.objects.get(session_id=session_id, user=user)
            except CareerSession.DoesNotExist:
                return Response(
                    {'error': 'Career & Degree Selection session not found'},
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


class CareerRecommendationsGenerateView(APIView):
    """Generate career recommendations based on conversation"""
    permission_classes = []

    @extend_schema(
        summary="Generate Career Recommendations",
        description="Analyzes the conversation and generates personalized career recommendations using AI.",
        responses={
            200: CareerRecommendationSerializer(many=True),
            400: OpenApiResponse(description="Invalid request"),
            404: OpenApiResponse(description="Session not found"),
        }
    )
    def post(self, request, session_id):
        try:
            session = career_discovery_service.get_session_by_id(session_id)
            if not session:
                return Response(
                    {'error': 'Career & Degree Selection session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check if there are enough messages for recommendations
            message_count = CareerMessage.objects.filter(session=session, type='user').count()
            if message_count < 3:
                return Response(
                    {'error': 'Not enough conversation data. Please complete more questions first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Generate recommendations
            result = career_discovery_service.generate_recommendations(session)
            
            # Refresh session to get latest token usage
            session.refresh_from_db(fields=['token_usage'])
            
            return Response({
                'session_id': session_id,
                'recommendations': result,
                'total_count': len(result),
                'token_usage': session.token_usage or {}
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'Failed to generate career recommendations: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CareerRecommendationsGetView(APIView):
    """Get stored career recommendations for a session"""
    permission_classes = []

    @extend_schema(
        summary="Get Career Recommendations",
        description="Returns previously generated career recommendations for a session.",
        responses={
            200: CareerRecommendationSerializer(many=True),
            404: OpenApiResponse(description="Session not found"),
        }
    )
    def get(self, request, session_id):
        try:
            session = career_discovery_service.get_session_by_id(session_id)
            if not session:
                return Response(
                    {'error': 'Career & Degree Selection session not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            recommendations = career_discovery_service.get_stored_recommendations(session)

            return Response({
                'session_id': session_id,
                'recommendations': recommendations,
                'total_count': len(recommendations)
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to get career recommendations: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CareerHealthCheckView(APIView):
    """Health check for Career & Degree Selection service"""
    permission_classes = []

    @extend_schema(
        summary="Health Check",
        description="Check if the Career & Degree Selection service is operational.",
        responses={
            200: OpenApiResponse(description="Service is healthy"),
        }
    )
    def get(self, request):
        try:
            # Try to initialize the LangChain service to check if Azure OpenAI is configured
            from .langchain_service import career_langchain_service
            
            return Response({
                'status': 'healthy',
                'service': 'career_discovery',
                'langchain_initialized': career_langchain_service._is_initialized,
                'message': 'Career & Degree Selection API is operational'
            })
        except Exception as e:
            return Response({
                'status': 'degraded',
                'service': 'career_discovery',
                'error': str(e),
                'message': 'Career & Degree Selection API may have configuration issues'
            })


class CareerSessionDebugView(APIView):
    """Get debug information for a Career & Degree Selection session"""
    permission_classes = []

    @extend_schema(
        summary="Get Session Debug Info",
        description="Returns debug information including system prompts, model info, and user context for a Career & Degree Selection session.",
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

            session = career_discovery_service.get_session_by_id(session_id)
            if not session:
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

            from .langchain_service import (
                career_langchain_service,
                CAREER_DISCOVERY_SYSTEM_PROMPT,
                RECOMMENDATIONS_SYSTEM_PROMPT,
            )
            from utils.azure_openai import get_azure_openai_config

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
                'max_tokens': 200,
            }
            recommendations_llm_info = {
                'type': 'AzureChatOpenAI',
                'model': deployment,
                'temperature': 0.7,
                'max_tokens': 8000,
            }

            # User context
            user_profile = get_user_profile_data(user)
            _user_name = getattr(user, 'first_name', '') or ''

            # Domain context (if session has a linked domain session)
            domain_context = {}
            if session.domain_session:
                try:
                    # Get domain recommendations from the linked domain session
                    domain_recommendations = session.domain_session.recommendations.all()
                    if domain_recommendations:
                        domain_context = {
                            'recommendations': [
                                {
                                    'title': rec.domain_title,
                                    'match_percentage': rec.match_percentage,
                                    'explanation': rec.why_recommended,
                                }
                                for rec in domain_recommendations
                            ],
                            'messages': []  # Domain messages not needed for debug
                        }
                except Exception as e:
                    print(f"Error fetching domain context: {e}")

            # Build the FULL enhanced system prompt using the centralized function
            static_prompt, enhanced_explorer_prompt = career_langchain_service._build_enhanced_system_prompt(
                user_profile=user_profile,
                domain_context=domain_context,
                current_step=session.current_step,
                agent_guidance="",
                debug_label="DEBUG ENDPOINT - ENHANCED SYSTEM PROMPT",
                user_name=_user_name,
            )
            
            # Also get formatted contexts separately for inspection
            user_context = format_user_profile_context(user_profile or {}, user_name=_user_name)
            domain_ctx_formatted = career_langchain_service.format_domain_context_for_prompt(domain_context)

            # Session state
            profile_messages = session.messages.filter(phase='profile').count()
            explorer_messages = session.messages.filter(phase='explorer').count()
            profile_questions = session.messages.filter(phase='profile', type='bot').count()
            explorer_questions = session.messages.filter(phase='explorer', type='bot').count()

            debug_info = {
                'session_id': session.session_id,
                'current_phase': session.current_phase,
                'model_info': {
                    'provider': 'Azure OpenAI',
                    'main_llm': main_llm_info,
                    'recommendations_llm': recommendations_llm_info,
                },
                'system_prompts': {
                    'base_explorer_prompt': CAREER_DISCOVERY_SYSTEM_PROMPT,
                    'explorer_question_prompt': static_prompt + enhanced_explorer_prompt,
                    'recommendations_prompt': RECOMMENDATIONS_SYSTEM_PROMPT,
                },
                'user_context': user_context,
                'domain_context': domain_ctx_formatted,
                'session_state': {
                    'current_step': session.current_step,
                    'total_steps': session.total_steps,
                    'profile_completed': profile_messages,
                    'explorer_completed': explorer_messages,
                    'profile_questions_count': profile_questions,
                    'explorer_questions_count': explorer_questions,
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
