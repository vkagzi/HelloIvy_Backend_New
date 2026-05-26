"""
Django management command: analyze_session_recordings
=====================================================

Uses LangChain agents to analyze student counsellor session transcriptions
and extract actionable learnings for improving Career & Degree Selection prompts.

The transcription .txt files live in:
    audio-recordings/outputs/*_transcription.txt

Usage:
    # Analyze all transcriptions individually
    python manage.py analyze_session_recordings --action individual --model gpt

    # Analyze a single transcription
    python manage.py analyze_session_recordings --action individual --model gpt --file akshay

    # Consolidate all individual reports
    python manage.py analyze_session_recordings --action consolidate --model gpt

    # Generate a prompt enhancement patch
    python manage.py analyze_session_recordings --action generate --model gpt

    # Full pipeline: individual → consolidate → generate
    python manage.py analyze_session_recordings --action all --model gpt

    # Force re-analysis (overwrite existing reports)
    python manage.py analyze_session_recordings --action all --model gpt --force

    # Use LangGraph agent mode (tool-calling) instead of direct LLM
    python manage.py analyze_session_recordings --action individual --model gpt --use-agent

    # Apply the generated prompt patch to constants.py (dry-run)
    python manage.py analyze_session_recordings --action apply --dry-run

    # Apply the prompt patch for real
    python manage.py analyze_session_recordings --action apply
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = (
        "Analyze student counsellor session transcriptions using LangChain agents "
        "and extract learnings to improve Career & Degree Selection prompts."
    )

    # Paths
    BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # project root
    AUDIO_DIR = BASE_DIR / "audio-recordings"
    OUTPUT_DIR = AUDIO_DIR / "outputs"
    ANALYSIS_DIR = OUTPUT_DIR / "analysis"
    CAREER_DISCOVERY_DIR = BASE_DIR / "career_discovery"

    def add_arguments(self, parser):
        parser.add_argument(
            "--action",
            type=str,
            required=True,
            choices=["individual", "consolidate", "generate", "all", "apply", "status"],
            help=(
                "Action to perform: "
                "individual (analyze each transcription), "
                "consolidate (merge reports), "
                "generate (create prompt patch), "
                "all (full pipeline), "
                "apply (apply prompt patch to constants.py), "
                "status (show current state)"
            ),
        )
        parser.add_argument(
            "--model",
            type=str,
            choices=["gpt", "gemini"],
            default=None,
            help="LLM to use for analysis (required for individual/consolidate/generate/all)",
        )
        parser.add_argument(
            "--file",
            type=str,
            default=None,
            help="Analyze a single transcription by stem name (e.g. 'akshay')",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force re-analysis even if reports already exist",
        )
        parser.add_argument(
            "--use-agent",
            action="store_true",
            help="Use LangGraph ReAct agent with tool-calling (instead of direct LLM)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="For 'apply' action: show changes without writing to files",
        )

    def handle(self, *args, **options):
        action = options["action"]

        if action == "status":
            self._show_status()
            return

        if action == "apply":
            self._apply_patch(dry_run=options["dry_run"])
            return

        # All other actions require --model
        model = options.get("model")
        if not model:
            raise CommandError(f"--model is required for action '{action}'")

        # Lazy import — add audio-recordings dir to path so we can import the analyzer
        audio_dir = str(self.AUDIO_DIR)
        if audio_dir not in sys.path:
            sys.path.insert(0, audio_dir)

        from analyze_transcriptions import (  # noqa: E402
            get_llm,
            analyze_individual,
            analyze_individual_with_agent,
            consolidate_reports,
            generate_prompt_patch,
            get_transcription_stems,
        )

        llm = get_llm(model)
        force = options["force"]
        use_agent = options["use_agent"]
        file_stem = options.get("file")

        if action == "individual":
            self._run_individual(llm, file_stem, force, use_agent)
        elif action == "consolidate":
            self._run_consolidate(llm, force)
        elif action == "generate":
            self._run_generate(llm, force)
        elif action == "all":
            self._run_all(llm, file_stem, force, use_agent)

    # ----------------------------------------------------------------
    # Action handlers
    # ----------------------------------------------------------------

    def _run_individual(self, llm, file_stem, force, use_agent):
        from analyze_transcriptions import (
            analyze_individual,
            analyze_individual_with_agent,
            get_transcription_stems,
        )

        stems = [file_stem] if file_stem else get_transcription_stems()
        if not stems:
            self.stderr.write(self.style.ERROR("No transcription files found."))
            return

        self.stdout.write(self.style.SUCCESS(f"Analyzing {len(stems)} transcription(s)..."))

        for stem in stems:
            self.stdout.write(f"  Processing: {stem}")
            if use_agent:
                analyze_individual_with_agent(llm, stem, force=force)
            else:
                analyze_individual(llm, stem, force=force)

        self.stdout.write(self.style.SUCCESS(f"Individual analysis complete. Reports in: {self.ANALYSIS_DIR}"))

    def _run_consolidate(self, llm, force):
        from analyze_transcriptions import consolidate_reports

        consolidate_reports(llm, force=force)
        self.stdout.write(self.style.SUCCESS("Consolidation complete."))

    def _run_generate(self, llm, force):
        from analyze_transcriptions import generate_prompt_patch

        patch = generate_prompt_patch(llm, force=force)
        self.stdout.write(self.style.SUCCESS("Prompt patch generated."))

        raw = patch.get("raw_prompt_patch", "")
        if raw:
            self.stdout.write(f"\n--- Prompt Patch Preview (first 500 chars) ---\n{raw[:500]}...")

    def _run_all(self, llm, file_stem, force, use_agent):
        from analyze_transcriptions import (
            analyze_individual,
            analyze_individual_with_agent,
            consolidate_reports,
            generate_prompt_patch,
            get_transcription_stems,
        )

        stems = [file_stem] if file_stem else get_transcription_stems()
        if not stems:
            self.stderr.write(self.style.ERROR("No transcription files found."))
            return

        # Step 1
        self.stdout.write(self.style.SUCCESS(f"\n=== STEP 1/3: Individual Analysis ({len(stems)} files) ==="))
        for stem in stems:
            self.stdout.write(f"  Processing: {stem}")
            if use_agent:
                analyze_individual_with_agent(llm, stem, force=force)
            else:
                analyze_individual(llm, stem, force=force)

        # Step 2
        self.stdout.write(self.style.SUCCESS("\n=== STEP 2/3: Consolidation ==="))
        consolidate_reports(llm, force=force)

        # Step 3
        self.stdout.write(self.style.SUCCESS("\n=== STEP 3/3: Prompt Patch Generation ==="))
        generate_prompt_patch(llm, force=force)

        self.stdout.write(self.style.SUCCESS("\nFull pipeline complete."))
        self._show_status()

    # ----------------------------------------------------------------
    # Status
    # ----------------------------------------------------------------

    def _show_status(self):
        """Show the current state of transcriptions and analyses."""
        self.stdout.write(self.style.SUCCESS("\n=== Transcription & Analysis Status ===\n"))

        # Transcriptions
        txt_files = sorted(self.OUTPUT_DIR.glob("*_transcription.txt")) if self.OUTPUT_DIR.exists() else []
        self.stdout.write(f"Transcription files: {len(txt_files)}")
        for f in txt_files:
            size_kb = f.stat().st_size / 1024
            self.stdout.write(f"  - {f.stem.replace('_transcription', '')} ({size_kb:.0f} KB)")

        # Analysis reports
        analysis_files = sorted(self.ANALYSIS_DIR.glob("*_analysis.json")) if self.ANALYSIS_DIR.exists() else []
        analyzed = [f for f in analysis_files if "consolidated" not in f.name]
        self.stdout.write(f"\nIndividual analysis reports: {len(analyzed)}")
        for f in analyzed:
            self.stdout.write(f"  - {f.stem.replace('_analysis', '')}")

        # Consolidated
        consolidated = self.ANALYSIS_DIR / "consolidated_learnings.json" if self.ANALYSIS_DIR.exists() else None
        if consolidated and consolidated.exists():
            self.stdout.write(self.style.SUCCESS("\nConsolidated report: YES"))
        else:
            self.stdout.write(self.style.WARNING("\nConsolidated report: NOT YET"))

        # Prompt patch
        patch = self.ANALYSIS_DIR / "prompt_patch.json" if self.ANALYSIS_DIR.exists() else None
        if patch and patch.exists():
            self.stdout.write(self.style.SUCCESS("Prompt patch: YES"))
            patch_md = self.ANALYSIS_DIR / "prompt_patch.md"
            if patch_md.exists():
                self.stdout.write(self.style.SUCCESS(f"Prompt patch (Markdown): YES ({patch_md.stat().st_size / 1024:.0f} KB)"))
        else:
            self.stdout.write(self.style.WARNING("Prompt patch: NOT YET"))

        # Missing analyses
        analyzed_stems = {f.stem.replace("_analysis", "") for f in analyzed}
        txt_stems = {f.stem.replace("_transcription", "") for f in txt_files}
        missing = txt_stems - analyzed_stems
        if missing:
            self.stdout.write(self.style.WARNING(f"\nNot yet analyzed: {', '.join(sorted(missing))}"))

    # ----------------------------------------------------------------
    # Apply prompt patch
    # ----------------------------------------------------------------

    def _apply_patch(self, dry_run: bool = False):
        """Apply the generated prompt patch to career_discovery/constants.py."""
        patch_path = self.ANALYSIS_DIR / "prompt_patch.json"
        patch_md_path = self.ANALYSIS_DIR / "prompt_patch.md"

        if not patch_path.exists():
            raise CommandError(
                "No prompt patch found. Run with --action generate first."
            )

        patch = json.loads(patch_path.read_text(encoding="utf-8"))
        raw_patch = patch.get("raw_prompt_patch", "")

        if not raw_patch and patch_md_path.exists():
            raw_patch = patch_md_path.read_text(encoding="utf-8")

        if not raw_patch:
            raise CommandError("Prompt patch is empty — nothing to apply.")

        constants_path = self.CAREER_DISCOVERY_DIR / "constants.py"
        if not constants_path.exists():
            raise CommandError(f"constants.py not found at {constants_path}")

        # Read current constants
        current = constants_path.read_text(encoding="utf-8")

        # Build the learnings section to inject
        learnings_section = self._build_learnings_constant(raw_patch, patch)

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\n=== DRY RUN — Changes that would be applied ===\n"))
            self.stdout.write(learnings_section)
            self.stdout.write(self.style.WARNING(
                "\nThis would be added to career_discovery/constants.py as "
                "SESSION_RECORDING_LEARNINGS_PROMPT"
            ))
            return

        # Check if the constant already exists
        if "SESSION_RECORDING_LEARNINGS_PROMPT" in current:
            # Replace existing
            import re
            pattern = r'SESSION_RECORDING_LEARNINGS_PROMPT\s*=\s*""".*?"""'
            if re.search(pattern, current, re.DOTALL):
                updated = re.sub(pattern, learnings_section.strip(), current, flags=re.DOTALL)
                constants_path.write_text(updated, encoding="utf-8")
                self.stdout.write(self.style.SUCCESS("Updated SESSION_RECORDING_LEARNINGS_PROMPT in constants.py"))
            else:
                self.stderr.write(self.style.ERROR("Could not locate existing constant to replace."))
                return
        else:
            # Append before the CAREER_AGENTS dict
            marker = "CAREER_AGENTS = {"
            if marker in current:
                insertion = f"\n\n{learnings_section}\n\n"
                updated = current.replace(marker, insertion + marker)
                constants_path.write_text(updated, encoding="utf-8")
                self.stdout.write(self.style.SUCCESS(
                    "Added SESSION_RECORDING_LEARNINGS_PROMPT to constants.py "
                    "(inserted before CAREER_AGENTS)"
                ))
            else:
                # Fallback: append to end
                constants_path.write_text(current + f"\n\n{learnings_section}\n", encoding="utf-8")
                self.stdout.write(self.style.SUCCESS(
                    "Appended SESSION_RECORDING_LEARNINGS_PROMPT to end of constants.py"
                ))

        # Also update langchain_service.py to reference the new constant
        self._update_langchain_service(patch)

    def _build_learnings_constant(self, raw_patch: str, patch: Dict[str, Any]) -> str:
        """Build the Python constant string."""
        # Escape triple quotes in the patch content
        escaped = raw_patch.replace('"""', '\\"\\"\\"')

        lines = [
            '# ================== SESSION RECORDING LEARNINGS ==================',
            f'# Auto-generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            f'# Based on analysis of {patch.get("total_sessions_informing", "N/A")} real counsellor-student sessions',
            '',
            f'SESSION_RECORDING_LEARNINGS_PROMPT = """',
            '<real_session_learnings>',
            '',
            escaped,
            '',
            '</real_session_learnings>',
            '"""',
        ]
        return "\n".join(lines)

    def _update_langchain_service(self, patch: Dict[str, Any]):
        """Add import and reference to SESSION_RECORDING_LEARNINGS_PROMPT in langchain_service.py."""
        service_path = self.CAREER_DISCOVERY_DIR / "langchain_service.py"
        if not service_path.exists():
            return

        content = service_path.read_text(encoding="utf-8")

        # Check if already imported
        if "SESSION_RECORDING_LEARNINGS_PROMPT" in content:
            self.stdout.write("  langchain_service.py already references SESSION_RECORDING_LEARNINGS_PROMPT")
            return

        # Add to imports
        old_import = "from .constants import ("
        new_import = "from .constants import (\n    SESSION_RECORDING_LEARNINGS_PROMPT,"
        if old_import in content:
            content = content.replace(old_import, new_import, 1)

        # Inject into CAREER_DISCOVERY_SYSTEM_PROMPT
        # Find where CAREER_DISCOVERY_SYSTEM_PROMPT is defined and add the learnings
        old_prompt_start = 'CAREER_DISCOVERY_SYSTEM_PROMPT = COUNSELOR_BEST_PRACTICES_PROMPT + """'
        new_prompt_start = 'CAREER_DISCOVERY_SYSTEM_PROMPT = COUNSELOR_BEST_PRACTICES_PROMPT + SESSION_RECORDING_LEARNINGS_PROMPT + """'
        if old_prompt_start in content:
            content = content.replace(old_prompt_start, new_prompt_start, 1)
            service_path.write_text(content, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(
                "  Updated langchain_service.py: added SESSION_RECORDING_LEARNINGS_PROMPT to system prompt"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "  Could not auto-inject into langchain_service.py — "
                "manually add SESSION_RECORDING_LEARNINGS_PROMPT to CAREER_DISCOVERY_SYSTEM_PROMPT"
            ))
