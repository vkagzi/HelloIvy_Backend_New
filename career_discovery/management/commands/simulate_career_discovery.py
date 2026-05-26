"""
Management command to simulate a complete Career & Degree Selection session.

Runs like a real conversation: the loop continues for all 20 Career & Degree Selection 
questions (fixed count), then generates career recommendations automatically.

Three ways to resolve the required Stream & Subject Selection prerequisite:

  1. Default — use the last completed domain session for the user:
       python manage.py simulate_career_discovery --email test@example.com

  2. Run a new Stream & Subject Selection simulation first, then Career & Degree Selection :
       python manage.py simulate_career_discovery --email test@example.com --run-domain-discovery

  3. Point to a specific completed domain session by ID:
       python manage.py simulate_career_discovery --email test@example.com --domain-session-id domain_abc123

Optional flags:
    --persona        arts | engineering | entrepreneurship | science | healthcare | random  (default: arts)
    --verbose        Show full question/answer text for each turn
    --dry-run        Show what would be done without making any changes
"""
import time
import random
from django.core.management.base import BaseCommand
from apps.accounts.models import User
from career_discovery.models import CareerSession, CareerMessage, CareerRecommendation
from career_discovery.services import CareerDiscoveryService
from career_discovery.simulated_user_agent import SimulatedCareerUserAgent, PERSONA_ENHANCEMENTS
from domain_discovery.models import DomainSession, DomainRecommendation
from domain_discovery.services import DomainDiscoveryService
from domain_discovery.simulated_user_agent import SimulatedUserAgent as DomainSimulatedUserAgent


AVAILABLE_PERSONAS = ['arts', 'engineering', 'entrepreneurship', 'science', 'healthcare']
TOTAL_CAREER_QUESTIONS = 20


class Command(BaseCommand):
    help = 'Simulate a complete Career & Degree Selection session (with optional auto Stream & Subject Selection) and generate recommendations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Email of the user to run the simulation for',
        )
        parser.add_argument(
            '--persona',
            type=str,
            choices=['arts', 'engineering', 'entrepreneurship', 'science', 'healthcare', 'random'],
            default='arts',
            help='The persona to simulate (use "random" for a randomly selected persona)',
        )
        parser.add_argument(
            '--domain-session-id',
            type=str,
            default=None,
            help='Use a specific completed domain session ID',
        )
        parser.add_argument(
            '--run-domain-discovery',
            action='store_true',
            help='Run a new Stream & Subject Selection simulation before Career & Degree Selection (instead of reusing the last session)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each question/answer',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        email = options['email']
        persona = options['persona']
        domain_session_id = options['domain_session_id']
        run_new_domain = options['run_domain_discovery']
        verbose = options['verbose']
        dry_run = options['dry_run']

        # Resolve 'random' to an actual persona
        if persona == 'random':
            persona = random.choice(AVAILABLE_PERSONAS)
            self.stdout.write(self.style.WARNING(f"Randomly selected persona: {persona.upper()}"))

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Career & Degree Selection Session Simulation")
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"User: {email}")
        self.stdout.write(f"Persona: {persona.upper()}")
        self.stdout.write(f"Mode: DYNAMIC (LLM-generated responses)")
        self.stdout.write(f"Career questions: {TOTAL_CAREER_QUESTIONS} (fixed)")
        if domain_session_id:
            domain_mode = f"specific session: {domain_session_id}"
        elif run_new_domain:
            domain_mode = "run new Stream & Subject Selection simulation"
        else:
            domain_mode = "use last completed domain session (default)"
        self.stdout.write(f"Domain session: {domain_mode}")
        self.stdout.write(f"Dry Run: {dry_run}")
        self.stdout.write(f"{'='*60}\n")

        # Get user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User with email {email} not found."))
            self.stdout.write("Tip: Create a user first with 'python manage.py create_test_user_profile'")
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — No changes will be made\n"))
            self._show_simulation_plan(persona, domain_session_id, run_new_domain)
            return

        # ──────────────────────────────────────────────────────────
        # Phase 1: Resolve or run Stream & Subject Selection
        # ──────────────────────────────────────────────────────────
        domain_session = self._resolve_domain_session(user, persona, domain_session_id, run_new_domain, verbose)
        if domain_session is None:
            return  # error already printed

        # ──────────────────────────────────────────────────────────
        # Phase 2: Career & Degree Selection 
        # ──────────────────────────────────────────────────────────
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Phase 2: Career & Degree Selection ")
        self.stdout.write(f"{'='*60}\n")

        career_service = CareerDiscoveryService()

        # Fetch user profile + domain context for the simulated agent
        from utils.profile_helpers import get_user_profile_data
        user_profile = get_user_profile_data(user)
        domain_context = career_service.get_domain_discovery_context(
            # We need a temporary object to call this; build context manually
            type('_Tmp', (), {'domain_session': domain_session})()
        )

        # Initialize simulated career user agent
        self.stdout.write(self.style.HTTP_INFO("Initializing simulated career user agent..."))
        try:
            simulated_agent = SimulatedCareerUserAgent(
                persona=persona,
                user_profile=user_profile,
                domain_context=domain_context,
            )
            self.stdout.write(self.style.SUCCESS(f"  ✓ Agent initialized with persona: {persona}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Failed to initialize career agent: {e}"))
            return

        # Step 1: Create career session
        self.stdout.write(self.style.HTTP_INFO("\nStep 1: Creating Career & Degree Selection session..."))
        session = career_service.create_session(user, domain_session=domain_session)
        self.stdout.write(self.style.SUCCESS(f"  ✓ Session created: {session.session_id}"))

        # Wait briefly for background session-notes thread to finish
        self.stdout.write("  Waiting for background session notes generation...")
        self._wait_for_session_notes(session, timeout=30)

        # Step 2: Conversation loop (20 turns)
        self.stdout.write(self.style.HTTP_INFO(
            f"\nStep 2: Running career conversation ({TOTAL_CAREER_QUESTIONS} questions)..."
        ))

        question_num = 0

        while True:
            session.refresh_from_db()

            if session.is_completed:
                break

            # Get the latest bot question
            messages = career_service.get_session_messages(session)
            bot_messages = [m for m in messages if m['type'] == 'bot']

            if bot_messages:
                last_question = bot_messages[-1]['content']
                response_text = simulated_agent.generate_response(last_question)
            else:
                response_text = "I find this topic really interesting and would love to explore it more."
                last_question = '(no question yet)'

            question_num += 1

            if verbose:
                self.stdout.write(f"\n  [{question_num}] Bot: {last_question[:300]}")
                self.stdout.write(f"       You: {response_text[:300]}")
            else:
                phase = "Profile Builder" if session.current_step < 10 else "Career Explorer"
                self.stdout.write(
                    f"  Turn {question_num} | step {session.current_step}/{session.total_steps} | {phase}"
                )

            # Send the answer to the real service (same code path as production)
            response = career_service.process_message(session, response_text)
            session.refresh_from_db()

            if response.get('is_complete'):
                concluding_msg = response.get('bot_response', '')
                if concluding_msg:
                    self.stdout.write(self.style.SUCCESS(f"\n  Bot (concluding): {concluding_msg}"))
                break

        self.stdout.write(self.style.SUCCESS(
            f"\n  ✓ Career conversation completed after {question_num} turns"
        ))
        self.stdout.write(f"    Final step: {session.current_step}/{session.total_steps}")

        # Step 3: Generate career recommendations
        self.stdout.write(self.style.HTTP_INFO("\nStep 3: Generating career recommendations..."))
        try:
            recommendations_data = career_service.generate_recommendations(session)
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ Generated {len(recommendations_data)} career recommendations\n"
            ))
            for rec in recommendations_data:
                self.stdout.write(f"  Rank {rec.get('rank', '?')}: {rec.get('career_title', 'Unknown')}")
                self.stdout.write(f"    Match: {rec.get('match_percentage', '?')}%")
                self.stdout.write(f"    Why: {str(rec.get('why_recommended', ''))[:120]}...")
                skills = rec.get('required_skills', [])
                if skills:
                    self.stdout.write(f"    Skills: {', '.join(skills[:5])}")
                alignment = rec.get('alignment_points', [])
                if alignment:
                    self.stdout.write(f"    Alignment: {', '.join(str(a) for a in alignment[:3])}")
                self.stdout.write("")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Error generating recommendations: {str(e)}"))
            import traceback
            traceback.print_exc()

        # Final summary
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(self.style.SUCCESS("Career & Degree Selection Simulation Complete!"))
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"  Domain Session ID: {domain_session.session_id}")
        self.stdout.write(f"  Career Session ID: {session.session_id}")
        self.stdout.write(f"  User: {user.email}")
        self.stdout.write(f"  Persona: {persona}")
        self.stdout.write(f"  Career Messages: {CareerMessage.objects.filter(session=session).count()}")
        self.stdout.write(f"  Career Recommendations: {CareerRecommendation.objects.filter(session=session).count()}")
        # Token usage
        session.refresh_from_db()
        token_usage = session.token_usage or {}
        if token_usage:
            self.stdout.write(f"  Total Tokens: {token_usage.get('total_tokens', 0):,}")
            self.stdout.write(f"  Total LLM Calls: {token_usage.get('total_llm_calls', 0)}")
        self.stdout.write("")

    # ──────────────────────────────────────────────────────────
    # Stream & Subject Selection Resolution
    # ──────────────────────────────────────────────────────────

    def _resolve_domain_session(self, user, persona, domain_session_id, run_new_domain, verbose):
        """
        Resolve the domain session for this Career & Degree Selection simulation.

        Priority:
          1. --domain-session-id provided → fetch that specific session
          2. --run-domain-discovery flag  → simulate a new domain session
          3. default                      → use the last completed domain session
        """
        if domain_session_id:
            return self._fetch_existing_domain_session(domain_session_id)
        elif run_new_domain:
            return self._run_domain_discovery_simulation(user, persona, verbose)
        else:
            return self._fetch_last_completed_domain_session(user)

    def _fetch_last_completed_domain_session(self, user):
        """Find and validate the most recently completed domain session for the user."""
        self.stdout.write(self.style.HTTP_INFO(
            "Looking for last completed domain session..."
        ))

        # Get the most recently completed domain session that has recommendations
        domain_session = (
            DomainSession.objects
            .filter(user=user)
            .order_by('-created_at')
            .first()
        )

        if domain_session is None:
            self.stdout.write(self.style.ERROR(
                "No Stream & Subject Selection session found for this user.\n"
                "Run Stream & Subject Selection first, or use --run-domain-discovery to simulate one."
            ))
            return None

        if not domain_session.is_completed:
            self.stdout.write(self.style.ERROR(
                f"The most recent domain session '{domain_session.session_id}' is not completed "
                f"(step {domain_session.current_step}/{domain_session.total_steps}).\n"
                "Complete it first, or use --run-domain-discovery to simulate a new one."
            ))
            return None

        rec_count = DomainRecommendation.objects.filter(session=domain_session).count()
        if rec_count == 0:
            self.stdout.write(self.style.ERROR(
                f"Domain session '{domain_session.session_id}' has no recommendations.\n"
                "Generate domain recommendations first, or use --run-domain-discovery."
            ))
            return None

        self.stdout.write(self.style.SUCCESS(
            f"  ✓ Using domain session: {domain_session.session_id} "
            f"({rec_count} recommendations)"
        ))
        return domain_session

    def _fetch_existing_domain_session(self, domain_session_id):
        """Fetch and validate an existing domain session."""
        self.stdout.write(self.style.HTTP_INFO(
            f"Using existing domain session: {domain_session_id}"
        ))
        try:
            domain_session = DomainSession.objects.get(session_id=domain_session_id)
        except DomainSession.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"Domain session '{domain_session_id}' not found."
            ))
            return None

        if not domain_session.is_completed:
            self.stdout.write(self.style.ERROR(
                f"Domain session '{domain_session_id}' is not completed "
                f"(step {domain_session.current_step}/{domain_session.total_steps}). "
                "Career & Degree Selection requires a completed domain session."
            ))
            return None

        rec_count = DomainRecommendation.objects.filter(session=domain_session).count()
        if rec_count == 0:
            self.stdout.write(self.style.ERROR(
                f"Domain session '{domain_session_id}' has no recommendations. "
                "Run recommendation generation first."
            ))
            return None

        self.stdout.write(self.style.SUCCESS(
            f"  ✓ Domain session valid — {rec_count} recommendations found"
        ))
        return domain_session

    def _run_domain_discovery_simulation(self, user, persona, verbose):
        """Run a complete Stream & Subject Selection simulation and return the concluded session."""
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Phase 1: Stream & Subject Selection (prerequisite)")
        self.stdout.write(f"{'='*60}\n")

        domain_service = DomainDiscoveryService()

        # Fetch real user profile
        from utils.profile_helpers import get_user_profile_data
        user_profile = get_user_profile_data(user)

        # Initialize domain simulated agent
        self.stdout.write(self.style.HTTP_INFO("Initializing Stream & Subject Selection simulated agent..."))
        try:
            domain_agent = DomainSimulatedUserAgent(persona=persona, user_profile=user_profile)
            self.stdout.write(self.style.SUCCESS(f"  ✓ Domain agent initialized with persona: {persona}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Failed to initialize domain agent: {e}"))
            return None

        # Create domain session
        self.stdout.write(self.style.HTTP_INFO("Creating Stream & Subject Selection session..."))
        domain_session = domain_service.create_session(user)
        self.stdout.write(self.style.SUCCESS(f"  ✓ Domain session created: {domain_session.session_id}"))

        # Run domain conversation loop
        self.stdout.write(self.style.HTTP_INFO(
            f"Running domain conversation "
            f"(min {DomainSession.MIN_DEEPDIVE_QUESTIONS}, max {DomainSession.MAX_DEEPDIVE_QUESTIONS})..."
        ))

        question_num = 0
        conclusion_reason = 'unknown'

        while True:
            domain_session.refresh_from_db()

            if domain_session.is_completed:
                conclusion_reason = 'background-conclusion (detected before next turn)'
                break

            messages = domain_service.get_session_messages(domain_session)
            bot_messages = [m for m in messages if m['type'] == 'bot']

            if bot_messages:
                last_question = bot_messages[-1]['content']
                response_text = domain_agent.generate_response(last_question)
            else:
                response_text = "I find this topic really interesting and would love to explore it more."
                last_question = '(no question yet)'

            question_num += 1

            if verbose:
                self.stdout.write(f"\n  [Domain Q{question_num}] Bot: {last_question[:200]}")
                self.stdout.write(f"                   You: {response_text[:200]}")
            else:
                self.stdout.write(
                    f"  Domain Turn {question_num} | "
                    f"step {domain_session.current_step}/{domain_session.total_steps}"
                )

            response = domain_service.process_message(domain_session, response_text)
            domain_session.refresh_from_db()

            if response.get('is_complete'):
                if domain_session.current_step >= DomainSession.MAX_DEEPDIVE_QUESTIONS:
                    conclusion_reason = f'hard cap ({DomainSession.MAX_DEEPDIVE_QUESTIONS} questions)'
                else:
                    conclusion_reason = 'LLM-driven conclusion'
                break

            # Wait for background conclusion check after minimum questions
            if domain_session.current_step >= DomainSession.MIN_DEEPDIVE_QUESTIONS:
                self._wait_for_domain_conclusion(domain_session, timeout=45)

        self.stdout.write(self.style.SUCCESS(
            f"\n  ✓ Domain session concluded after {question_num} turns — reason: {conclusion_reason}"
        ))

        # Generate domain recommendations
        self.stdout.write(self.style.HTTP_INFO("Generating domain recommendations..."))
        try:
            domain_recs = domain_service.generate_recommendations(domain_session)
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ Generated {len(domain_recs)} domain recommendations"
            ))
            for rec in domain_recs:
                self.stdout.write(f"    • {rec.domain_title} ({rec.match_percentage}% match)")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Error generating domain recommendations: {e}"))
            return None

        return domain_session

    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────

    def _wait_for_domain_conclusion(self, session, timeout: int = 45):
        """Poll DB until the background domain-conclusion check writes its result
        or timeout expires.  Mirrors simulate_domain_discovery behaviour."""
        poll_interval = 1
        elapsed = 0
        step_at_launch = session.current_step

        while elapsed < timeout:
            time.sleep(poll_interval)
            elapsed += poll_interval
            session.refresh_from_db()

            if session.metadata and 'should_conclude' in session.metadata:
                last_checked = session.metadata.get('last_checked_step', -1)
                if last_checked >= step_at_launch:
                    if session.metadata['should_conclude']:
                        self.stdout.write(
                            self.style.WARNING(
                                f"    [wait] Domain conclusion check done after {elapsed}s — should_conclude=True"
                            )
                        )
                    else:
                        if elapsed > 3:
                            self.stdout.write(
                                f"    [wait] Domain conclusion check done after {elapsed}s — continue"
                            )
                    return

            if session.is_completed:
                self.stdout.write(
                    self.style.WARNING(f"    [wait] Domain session marked complete after {elapsed}s")
                )
                return

        self.stdout.write(
            self.style.WARNING(f"    [wait] Domain conclusion check timed out after {timeout}s — proceeding")
        )

    def _wait_for_session_notes(self, session, timeout: int = 30):
        """Poll for background session notes generation to complete."""
        poll_interval = 1
        elapsed = 0

        while elapsed < timeout:
            time.sleep(poll_interval)
            elapsed += poll_interval
            session.refresh_from_db()

            if session.notes:
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ Session notes ready ({len(session.notes)} chars, {elapsed}s)"
                ))
                return

        self.stdout.write(self.style.WARNING(
            f"  ⚠ Session notes not ready after {timeout}s — proceeding anyway"
        ))

    def _show_simulation_plan(self, persona, domain_session_id, run_new_domain):
        """Show what the simulation would do (for dry run)."""
        persona_data = PERSONA_ENHANCEMENTS.get(persona, PERSONA_ENHANCEMENTS['default'])

        self.stdout.write(f"Persona: {persona.upper()}")
        self.stdout.write(f"Speaking Style: {persona_data.get('speaking_style', 'natural')}")

        self.stdout.write(f"\nSimulation Plan:")

        if domain_session_id:
            self.stdout.write(f"  Phase 1 [mode 3]: Use specific domain session '{domain_session_id}'")
        elif run_new_domain:
            self.stdout.write(f"  Phase 1 [mode 2]: Run a new Stream & Subject Selection simulation")
            self.stdout.write(f"    1a. Create Stream & Subject Selection session")
            self.stdout.write(
                f"    1b. Loop: answer deepdive questions until LLM conclusion or "
                f"hard cap ({DomainSession.MAX_DEEPDIVE_QUESTIONS})"
            )
            self.stdout.write(f"    1c. Generate domain recommendations")
        else:
            self.stdout.write(f"  Phase 1 [mode 1 — default]: Use last completed domain session")
            self.stdout.write(f"    Error if no completed session or no recommendations found")

        self.stdout.write(f"  Phase 2: Career & Degree Selection simulation")
        self.stdout.write(f"    2a. Create Career & Degree Selection session (linked to domain session)")
        self.stdout.write(f"    2b. Wait for background session notes generation")
        self.stdout.write(f"    2c. Q1: Primary domain selection (from domain recommendations)")
        self.stdout.write(f"    2d. Q2: Secondary domain selection")
        self.stdout.write(f"    2e. Q3-Q{TOTAL_CAREER_QUESTIONS}: Career exploration questions")
        self.stdout.write(f"    2f. Generate career recommendations on completion")

        self.stdout.write(f"\nTotal career questions: {TOTAL_CAREER_QUESTIONS} (fixed)")
        self.stdout.write(f"Responses are dynamically generated by an LLM agent — different every run.")
        self.stdout.write("")
