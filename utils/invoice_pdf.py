"""
Generate a Tax Invoice PDF that mirrors the frontend InvoicePDF.tsx template.

Uses reportlab to produce an in-memory PDF (bytes) suitable for email attachment.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field

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
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

# ── Colours (matching frontend maroon theme) ──────────────────────────
MAROON = colors.HexColor("#8B0000")
BORDER_GRAY = colors.HexColor("#BBBBBB")
LABEL_BG = colors.HexColor("#F5F0F0")
WHITE = colors.white
LIGHT_GRAY = colors.HexColor("#FAFAFA")

# ── Logo ──────────────────────────────────────────────────────────────
_LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo_app.png")


# ── Data classes ──────────────────────────────────────────────────────
@dataclass
class InvoiceLineItem:
    module: str
    quantity: int
    price: int  # unit price in minor-denomination (e.g. INR whole rupees)


@dataclass
class InvoiceData:
    order_id: int
    order_date: str  # human-readable, e.g. "30 Apr 2026"
    billing_name: str
    first_name: str
    last_name: str
    email: str
    address: str = ""
    gst_number: str = ""
    line_items: list[InvoiceLineItem] = field(default_factory=list)
    subtotal: int = 0
    discount: int = 0
    discount_code: str | None = None
    tax: int = 0
    tax_label: str = "IGST (18%)"
    total: int = 0
    currency: str = "INR"
    transaction_id: str = ""
    status: str = ""
    payment_mode: str = ""


# ── Helpers ───────────────────────────────────────────────────────────
def _fmt_inr(amount: int) -> str:
    """Format amount as 'Rs 1,23,456.00' (Indian grouping)."""
    s = f"{amount:,.2f}"
    # Python's comma grouping uses Western style; convert to Indian.
    parts = s.split(".")
    integer_part = parts[0].replace(",", "")
    sign = ""
    if integer_part.startswith("-"):
        sign = "-"
        integer_part = integer_part[1:]
    if len(integer_part) <= 3:
        grouped = integer_part
    else:
        last3 = integer_part[-3:]
        rest = integer_part[:-3]
        chunks = []
        while rest:
            chunks.insert(0, rest[-2:])
            rest = rest[:-2]
        grouped = ",".join(chunks) + "," + last3
    return f"Rs {sign}{grouped}.{parts[1]}"


def _number_to_words(num: int) -> str:
    """Convert number to Indian English words, e.g. 'One thousand one hundred rupees'."""
    if num == 0:
        return "Zero rupees"

    ones = [
        "", "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
        "sixteen", "seventeen", "eighteen", "nineteen",
    ]
    tens = [
        "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
        "eighty", "ninety",
    ]

    def _convert(n: int) -> str:
        if n < 20:
            return ones[n]
        if n < 100:
            return tens[n // 10] + (" " + ones[n % 10] if n % 10 else "")
        if n < 1000:
            return ones[n // 100] + " hundred" + (" and " + _convert(n % 100) if n % 100 else "")
        if n < 100_000:
            return _convert(n // 1000) + " thousand" + (" " + _convert(n % 1000) if n % 1000 else "")
        if n < 1_00_00_000:
            return _convert(n // 100_000) + " lakh" + (" " + _convert(n % 100_000) if n % 100_000 else "")
        return _convert(n // 1_00_00_000) + " crore" + (" " + _convert(n % 1_00_00_000) if n % 1_00_00_000 else "")

    words = _convert(round(abs(num)))
    return words[0].upper() + words[1:] + " rupees"


def _module_label(module: str) -> str:
    return module.replace("_", " ").title()


# ── PDF Builder ───────────────────────────────────────────────────────
def generate_invoice_pdf(data: InvoiceData) -> bytes:
    """Return PDF bytes for the given invoice data."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=32,
        bottomMargin=28,
    )

    styles = getSampleStyleSheet()
    story: list = []

    # ── Styles ────────────────────────────────────────────────────────
    s_company_name = ParagraphStyle(
        "CompanyName", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=9, textColor=MAROON,
        alignment=TA_RIGHT,
    )
    s_company_line = ParagraphStyle(
        "CompanyLine", parent=styles["Normal"],
        fontName="Helvetica", fontSize=6.5, textColor=colors.HexColor("#555555"),
        alignment=TA_RIGHT, leading=9,
    )
    s_normal_small = ParagraphStyle(
        "NormalSmall", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8, leading=10,
    )
    s_disclaimer = ParagraphStyle(
        "Disclaimer", parent=styles["Normal"],
        fontName="Helvetica", fontSize=6.5, textColor=colors.HexColor("#666666"),
        leading=9,
    )
    s_footer = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontName="Helvetica", fontSize=7, textColor=colors.HexColor("#888888"),
        alignment=TA_CENTER,
    )

    page_width = A4[0] - 80  # minus margins

    # ── Header (logo + company info) ──────────────────────────────────
    logo_cell = ""
    if os.path.exists(_LOGO_PATH):
        logo_cell = Image(_LOGO_PATH, width=120, height=32)

    company_info = (
        f'<font face="Helvetica-Bold" size="9" color="{MAROON.hexval()}">Reach Education Pvt. Ltd.</font><br/>'
        '<font size="6.5" color="#555555">'
        "Mittal Tower, B Wing, 7th Floor, No. 71<br/>"
        "Nariman Point, Mumbai 400 021, India<br/>"
        "PAN: AAFCR7995F | GST: 27AAFCR7995F1ZS"
        "</font>"
    )
    company_para = Paragraph(company_info, s_company_line)

    header_table = Table(
        [[logo_cell, company_para]],
        colWidths=[page_width * 0.5, page_width * 0.5],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))

    # ── Title bar ─────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "InvoiceTitle", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=14, textColor=WHITE,
        alignment=TA_CENTER, spaceAfter=0, spaceBefore=0,
    )
    title_table = Table(
        [[Paragraph("TAX INVOICE", title_style)]],
        colWidths=[page_width],
    )
    title_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), MAROON),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(title_table)
    story.append(Spacer(1, 12))

    # ── Info grid ─────────────────────────────────────────────────────
    label_style = ParagraphStyle(
        "InfoLabel", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=7.5, textColor=colors.HexColor("#333333"),
    )
    value_style = ParagraphStyle(
        "InfoValue", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#111111"),
    )
    status_display = data.status.capitalize() if data.status else "-"

    info_data = [
        [
            Paragraph("Order ID:", label_style), Paragraph(str(data.order_id), value_style),
            Paragraph("Order Date:", label_style), Paragraph(data.order_date, value_style),
        ],
        [
            Paragraph("Billing Name:", label_style), Paragraph(data.billing_name, value_style),
            Paragraph("GST Number:", label_style), Paragraph(data.gst_number or "-", value_style),
        ],
        [
            Paragraph("First Name:", label_style), Paragraph(data.first_name, value_style),
            Paragraph("Email:", label_style), Paragraph(data.email, value_style),
        ],
        [
            Paragraph("Last Name:", label_style), Paragraph(data.last_name, value_style),
            Paragraph("Txn ID:", label_style), Paragraph(data.transaction_id or "-", value_style),
        ],
        [
            Paragraph("Payment Mode:", label_style), Paragraph(data.payment_mode or "-", value_style),
            Paragraph("Status:", label_style), Paragraph(status_display, value_style),
        ],
        [
            Paragraph("Billing Address:", label_style), Paragraph(data.address or "-", value_style),
            Paragraph("", label_style), Paragraph("", value_style),
        ],
    ]
    cw = [page_width * 0.17, page_width * 0.33, page_width * 0.17, page_width * 0.33]
    info_table = Table(info_data, colWidths=cw)
    info_style_cmds = [
        ("BOX", (0, 0), (-1, -1), 1, BORDER_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("SPAN", (1, 5), (3, 5)),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    # Label columns background
    for row_idx in range(5):
        info_style_cmds.append(("BACKGROUND", (0, row_idx), (0, row_idx), LABEL_BG))
        info_style_cmds.append(("BACKGROUND", (2, row_idx), (2, row_idx), LABEL_BG))
    info_style_cmds.append(("BACKGROUND", (0, 5), (0, 5), LABEL_BG))
    info_table.setStyle(TableStyle(info_style_cmds))
    story.append(info_table)
    story.append(Spacer(1, 14))

    # ── Line items table ──────────────────────────────────────────────
    hdr_style = ParagraphStyle(
        "TblHdr", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=8, textColor=WHITE,
    )
    cell_style = ParagraphStyle(
        "TblCell", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#222222"),
    )
    cell_r = ParagraphStyle("TblCellR", parent=cell_style, alignment=TA_RIGHT)
    cell_c = ParagraphStyle("TblCellC", parent=cell_style, alignment=TA_CENTER)
    hdr_r = ParagraphStyle("TblHdrR", parent=hdr_style, alignment=TA_RIGHT)
    hdr_c = ParagraphStyle("TblHdrC", parent=hdr_style, alignment=TA_CENTER)

    col_widths = [
        page_width * 0.08,
        page_width * 0.42,
        page_width * 0.18,
        page_width * 0.14,
        page_width * 0.18,
    ]

    table_data = [[
        Paragraph("S.No", hdr_style),
        Paragraph("Services", hdr_style),
        Paragraph("Price", hdr_r),
        Paragraph("Quantity", hdr_c),
        Paragraph("Total", hdr_r),
    ]]

    sessions_total = 0
    for i, item in enumerate(data.line_items, 1):
        sessions_total += item.quantity
        line_total = item.price * item.quantity
        table_data.append([
            Paragraph(str(i), cell_style),
            Paragraph(_module_label(item.module), cell_style),
            Paragraph(_fmt_inr(item.price), cell_r),
            Paragraph(str(item.quantity), cell_c),
            Paragraph(_fmt_inr(line_total), cell_r),
        ])

    # Grand total row
    bold_cell = ParagraphStyle("BoldCell", parent=cell_style, fontName="Helvetica-Bold")
    bold_cell_c = ParagraphStyle("BoldCellC", parent=bold_cell, alignment=TA_CENTER)
    table_data.append([
        Paragraph("", cell_style),
        Paragraph("Sessions Grand Total", bold_cell),
        Paragraph("", cell_style),
        Paragraph(str(sessions_total), bold_cell_c),
        Paragraph("", cell_style),
    ])

    items_table = Table(table_data, colWidths=col_widths)
    items_style_cmds = [
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), MAROON),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    # Data rows
    num_items = len(data.line_items)
    for row_idx in range(1, num_items + 1):
        items_style_cmds.append(("TOPPADDING", (0, row_idx), (-1, row_idx), 6))
        items_style_cmds.append(("BOTTOMPADDING", (0, row_idx), (-1, row_idx), 6))
        items_style_cmds.append(("LINEBELOW", (0, row_idx), (-1, row_idx), 0.5, colors.HexColor("#CCCCCC")))
        if row_idx % 2 == 0:
            items_style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), LIGHT_GRAY))
    # Grand total row
    gt_row = num_items + 1
    items_style_cmds.extend([
        ("BACKGROUND", (0, gt_row), (-1, gt_row), LABEL_BG),
        ("LINEABOVE", (0, gt_row), (-1, gt_row), 1.5, BORDER_GRAY),
        ("LINEBELOW", (0, gt_row), (-1, gt_row), 1.5, BORDER_GRAY),
        ("TOPPADDING", (0, gt_row), (-1, gt_row), 6),
        ("BOTTOMPADDING", (0, gt_row), (-1, gt_row), 6),
    ])
    items_table.setStyle(TableStyle(items_style_cmds))
    story.append(items_table)

    # ── Summary ───────────────────────────────────────────────────────
    story.append(Spacer(1, 10))
    sum_label = ParagraphStyle("SumLabel", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#444444"), alignment=TA_RIGHT)
    sum_value = ParagraphStyle("SumValue", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#222222"), alignment=TA_RIGHT)

    discount_label = "Discount"
    if data.discount_code:
        discount_label = f"Discount ({data.discount_code})"

    summary_rows = [
        [Paragraph("Sub-Total", sum_label), Paragraph(_fmt_inr(data.subtotal), sum_value)],
        [Paragraph(discount_label, sum_label), Paragraph(_fmt_inr(data.discount), sum_value)],
        [Paragraph("Addon ()", sum_label), Paragraph(_fmt_inr(0), sum_value)],
        [Paragraph(f"+ {data.tax_label}", sum_label), Paragraph(_fmt_inr(data.tax), sum_value)],
    ]
    sum_table = Table(summary_rows, colWidths=[page_width * 0.65, page_width * 0.35])
    sum_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(sum_table)

    # Grand total
    gt_label_style = ParagraphStyle("GTLabel", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, textColor=MAROON, alignment=TA_RIGHT)
    gt_value_style = ParagraphStyle("GTValue", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, textColor=MAROON, alignment=TA_RIGHT)
    gt_table = Table(
        [[Paragraph("Grand Total", gt_label_style), Paragraph(_fmt_inr(data.total), gt_value_style)]],
        colWidths=[page_width * 0.65, page_width * 0.35],
    )
    gt_table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, MAROON),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
    ]))
    story.append(gt_table)

    # Total in words
    words_style = ParagraphStyle("TotalWords", parent=styles["Normal"], fontName="Helvetica-Oblique", fontSize=7.5, textColor=colors.HexColor("#666666"), alignment=TA_RIGHT)
    story.append(Paragraph(_number_to_words(data.total), words_style))

    # ── Payment Terms ─────────────────────────────────────────────────
    story.append(Spacer(1, 18))
    terms_title_style = ParagraphStyle("TermsTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, textColor=WHITE)
    terms_style = ParagraphStyle("Terms", parent=styles["Normal"], fontName="Helvetica", fontSize=7, leading=10, textColor=colors.HexColor("#333333"))
    terms_bold = ParagraphStyle("TermsBold", parent=terms_style, fontName="Helvetica-Bold", fontSize=7.5, textColor=colors.HexColor("#222222"))

    left_terms = (
        '<font face="Helvetica-Bold" size="7.5" color="#222222">Cash Or Cheque:</font><br/>'
        "Cash payment limit - Rs.25,000/-<br/>"
        "Reach Education Pvt. Ltd.<br/>"
        "Mittal Tower, B Wing, 7th floor, No. 71<br/>"
        "Nariman Point, Mumbai 400 021, India<br/>"
        "Pan card number - AAFCR7995F<br/>"
        "GST number - 27AAFCR7995F1ZS<br/>"
        "Service accounting code (SAC) - 999293<br/>"
        "Description of Service: Commercial Training<br/>"
        "and Coaching Services"
    )
    right_terms = (
        '<font face="Helvetica-Bold" size="7.5" color="#222222">Bank Transfer:</font><br/>'
        "Beneficiary Name: Reach Education Pvt. Ltd<br/>"
        "Bank: HDFC<br/>"
        "City: Mumbai, India<br/>"
        "Account Type: Current<br/>"
        "Branch: Nariman Point<br/>"
        "Account #: 00012320009388<br/>"
        "Destination Bank: HDFC<br/>"
        "IFSC Code (Transfers from within India):<br/>"
        "HDFC0000001<br/>"
        "SWIFT Code (Transfers from outside India):<br/>"
        "HDFCINBB"
    )

    # Title row
    terms_header = Table(
        [[Paragraph("Payment Terms", terms_title_style)]],
        colWidths=[page_width],
    )
    terms_header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), MAROON),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(terms_header)

    terms_body = Table(
        [[Paragraph(left_terms, terms_style), Paragraph(right_terms, terms_style)]],
        colWidths=[page_width * 0.48, page_width * 0.48],
    )
    terms_body.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, MAROON),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEAFTER", (0, 0), (0, 0), 0.5, colors.HexColor("#DDDDDD")),
    ]))
    story.append(terms_body)

    # ── Disclaimer ────────────────────────────────────────────────────
    story.append(Spacer(1, 12))
    disclaimer_text = (
        "We do not offer any refund/exchange of services. Application Services can be deferred "
        "for up to 1 year by paying an admin/deferral fee. All stand-alone services are valid "
        "for 3 months from the date of the purchase. All comprehensive packages are valid till "
        "31st March of the financial year they are purchased in. Note: Banks require 24 hours "
        "to add a new user as a beneficiary."
    )
    story.append(Paragraph(disclaimer_text, s_disclaimer))

    # ── Footer ────────────────────────────────────────────────────────
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "ReachIvy™ - Registered Subsidiary of Reach Education. All Rights Reserved.",
        s_footer,
    ))

    doc.build(story)
    return buf.getvalue()
