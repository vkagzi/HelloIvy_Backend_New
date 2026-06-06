"""
Generate professional discovery session reports in PDF format.
Uses reportlab to produce an in-memory PDF (bytes) suitable for email attachment.
"""

from __future__ import annotations
import io
import os
from dataclasses import dataclass, field
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
    PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

# ── Colours (matching HelloIvy theme) ───────────────────────────────
MAROON = colors.HexColor("#7B0012")  # HelloIvy Maroon
BRAND_BLUE = colors.HexColor("#4f46e5")
BORDER_GRAY = colors.HexColor("#E5E7EB")
LABEL_BG = colors.HexColor("#F9FAFB")
WHITE = colors.white
LIGHT_GRAY = colors.HexColor("#F3F4F6")
TEXT_DARK = colors.HexColor("#111827")
TEXT_LIGHT = colors.HexColor("#4B5563")

# ── Logo ──────────────────────────────────────────────────────────────
_LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo_app.png")


@dataclass
class ReportData:
    student_name: str
    module_name: str
    session_id: str
    generated_at: str
    transcript: list[dict[str, str]] = field(default_factory=list)
    recommendations: list[dict[str, any]] = field(default_factory=list)


def generate_discovery_report_pdf(data: ReportData) -> bytes:
    """Return PDF bytes for the given discovery report data."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    story: list = []

    # ── Custom Styles ─────────────────────────────────────────────────
    s_title = ParagraphStyle(
        "ReportTitle", parent=styles["Heading1"],
        fontName="Helvetica-Bold", fontSize=24, textColor=MAROON,
        spaceAfter=12,
    )
    s_subtitle = ParagraphStyle(
        "ReportSubtitle", parent=styles["Normal"],
        fontName="Helvetica", fontSize=14, textColor=TEXT_LIGHT,
        spaceAfter=24,
    )
    s_section_header = ParagraphStyle(
        "SectionHeader", parent=styles["Heading2"],
        fontName="Helvetica-Bold", fontSize=16, textColor=TEXT_DARK,
        spaceBefore=20, spaceAfter=10,
        borderPadding=(0, 0, 5, 0),
    )
    s_label = ParagraphStyle(
        "Label", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=10, textColor=TEXT_DARK,
    )
    s_value = ParagraphStyle(
        "Value", parent=styles["Normal"],
        fontName="Helvetica", fontSize=10, textColor=TEXT_LIGHT,
    )
    s_transcript_bot = ParagraphStyle(
        "TranscriptBot", parent=styles["Normal"],
        fontName="Helvetica-Oblique", fontSize=10, textColor=MAROON,
        leftIndent=10, spaceBefore=6, spaceAfter=2,
    )
    s_transcript_user = ParagraphStyle(
        "TranscriptUser", parent=styles["Normal"],
        fontName="Helvetica", fontSize=10, textColor=TEXT_DARK,
        leftIndent=20, spaceAfter=8,
    )
    s_rec_title = ParagraphStyle(
        "RecTitle", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=12, textColor=MAROON,
    )
    s_rec_desc = ParagraphStyle(
        "RecDesc", parent=styles["Normal"],
        fontName="Helvetica", fontSize=10, textColor=TEXT_LIGHT,
        leading=14,
    )
    s_footer = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#9CA3AF"),
        alignment=TA_CENTER,
    )

    page_width = A4[0] - 40 * mm

    # ── Header ────────────────────────────────────────────────────────
    if os.path.exists(_LOGO_PATH):
        story.append(Image(_LOGO_PATH, width=40 * mm, height=10 * mm))
    story.append(Spacer(1, 10 * mm))

    story.append(Paragraph(f"{data.module_name} Report", s_title))
    story.append(Paragraph(f"Personalized insights for {data.student_name}", s_subtitle))

    # ── Meta Info ─────────────────────────────────────────────────────
    meta_data = [
        [Paragraph("Student Name:", s_label), Paragraph(data.student_name, s_value)],
        [Paragraph("Session ID:", s_label), Paragraph(data.session_id, s_value)],
        [Paragraph("Date Generated:", s_label), Paragraph(data.generated_at, s_value)],
    ]
    meta_table = Table(meta_data, colWidths=[40 * mm, page_width - 40 * mm])
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10 * mm))

    # ── Recommendations ────────────────────────────────────────────────
    story.append(Paragraph("Your Key Recommendations", s_section_header))
    
    for rec in data.recommendations:
        title = rec.get('career_title') or rec.get('domain_title') or rec.get('college_name') or "Recommendation"
        match = rec.get('match_percentage')
        desc = rec.get('description') or rec.get('why_recommended') or ""
        
        match_text = f" ({match}% Match)" if match else ""
        story.append(Paragraph(f"{title}{match_text}", s_rec_title))
        if desc:
            story.append(Paragraph(desc, s_rec_desc))
        
        # Sub-items if any (like related subjects or sub-domains)
        sub_items = rec.get('sub_domains') or rec.get('potential_careers') or []
        if sub_items:
            story.append(Paragraph(f"Explore: {', '.join(sub_items[:4])}", s_value))
            
        story.append(Spacer(1, 6 * mm))

    # ── Transcript ────────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("Conversation Transcript", s_section_header))
    
    for msg in data.transcript:
        bot_q = msg.get('bot_question') or msg.get('content')
        user_a = msg.get('student_response') or ""
        
        if bot_q:
            story.append(Paragraph(f"AI Coach: \"{bot_q}\"", s_transcript_bot))
        if user_a:
            story.append(Paragraph(f"You: {user_a}", s_transcript_user))
            
    # ── Footer ────────────────────────────────────────────────────────
    story.append(Spacer(1, 20 * mm))
    story.append(Paragraph(
        "HelloIvy™ - Discover Your Future. All Rights Reserved.",
        s_footer,
    ))

    doc.build(story)
    return buf.getvalue()
