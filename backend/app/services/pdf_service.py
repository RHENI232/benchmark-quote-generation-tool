"""
PDF Service for generating professional, customer-facing quotation documents.

Restricted to approved quotes. Strictly excludes internal cost prices, margins,
and internal approval logs. Reuses authoritative financial snapshots from the Quote model.
"""

from io import BytesIO
from pathlib import Path
from collections import OrderedDict
from datetime import datetime
from decimal import Decimal
from xml.sax.saxutils import escape as xml_escape

from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
LOGO_PATH = ROOT_DIR / "frontend" / "public" / "assets" / "logo.webp"

# Color Palette (Corporate Broadcast Blue & Slate)
COLOR_PRIMARY = colors.HexColor("#0F172A")       # Deep Slate / Navy
COLOR_SECONDARY = colors.HexColor("#1E293B")     # Charcoal Dark
COLOR_ACCENT = colors.HexColor("#2563EB")        # Royal Blue
COLOR_BORDER = colors.HexColor("#E2E8F0")        # Light Grey Border
COLOR_BORDER_DARK = colors.HexColor("#CBD5E1")   # Mid Grey Border
COLOR_MUTED = colors.HexColor("#64748B")         # Muted Slate Text
COLOR_BG_SECTION = colors.HexColor("#F8FAFC")    # Very Light Slate
COLOR_BG_TH = colors.HexColor("#1E293B")         # Dark Table Header


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute total page count ('Page X of Y')
    and render consistent running headers/footers.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self.quote_ref_no = ""

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(COLOR_MUTED)

        # Running header on page 2 and later
        if self._pageNumber > 1:
            self.drawString(36, 808, f"Quotation: {self.quote_ref_no}")
            self.drawRightString(559, 808, "Customer Copy")
            self.setStrokeColor(COLOR_BORDER_DARK)
            self.setLineWidth(0.5)
            self.line(36, 800, 559, 800)

        # Running footer on every page
        self.setStrokeColor(COLOR_BORDER)
        self.setLineWidth(0.5)
        self.line(36, 36, 559, 36)
        self.drawString(36, 24, "Confidential — Benchmark Broadcast Systems")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(559, 24, page_str)
        self.restoreState()


def _format_currency(amount, currency_code: str = "USD") -> str:
    """Format an amount with clean ASCII symbols to avoid missing font glyphs in Helvetica."""
    code = (currency_code or "USD").upper().strip()
    val = float(amount) if amount is not None else 0.0

    # Helvetica lacks the Indian Rupee glyph '₹' (U+20B9), causing a black square .notdef glyph.
    # Standard ASCII representation 'INR ' resolves this cleanly across all PDF viewers.
    if code == "INR":
        return f"INR {val:,.2f}"
    elif code == "USD":
        return f"${val:,.2f}"
    elif code == "SGD":
        return f"S${val:,.2f}"
    elif code == "EUR":
        return f"EUR {val:,.2f}"
    elif code == "GBP":
        return f"£{val:,.2f}"
    else:
        return f"{code} {val:,.2f}"


def _get_logo_flowable():
    """Load frontend/public/assets/logo.webp and convert to PNG in-memory."""
    try:
        if LOGO_PATH.exists():
            pil_img = PILImage.open(LOGO_PATH)
            png_buf = BytesIO()
            pil_img.save(png_buf, format="PNG")
            png_buf.seek(0)
            # Preserving ~6:1 aspect ratio (160 x 27 pt)
            return RLImage(png_buf, width=160, height=27)
    except Exception:
        pass
    # Fallback text if image cannot be loaded
    styles = getSampleStyleSheet()
    fallback_style = ParagraphStyle(
        "LogoFallback",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=COLOR_PRIMARY,
    )
    return Paragraph("BENCHMARK BROADCAST SYSTEMS", fallback_style)


def _group_line_items_by_section(line_items):
    """Group items by section preserving sort order."""
    sections = OrderedDict()
    sorted_items = sorted(
        line_items,
        key=lambda li: (li.section or "", li.sort_order if li.sort_order is not None else 0),
    )
    for item in sorted_items:
        key = item.section or "General Equipment & Services"
        sections.setdefault(key, []).append(item)
    return sections


def generate_customer_pdf(quote) -> BytesIO:
    """
    Generate a complete, customer-facing quotation PDF in memory.
    Strictly contains sell-side figures in the quote's display currency.
    """
    buf = BytesIO()
    # A4: 595.27 x 841.89 pt. Margins: 36 pt left/right -> 523.27 pt usable width.
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=46,
        bottomMargin=46,
    )

    currency = quote.currency_code or "USD"
    fx_rate = float(quote.fx_rate_to_usd) if quote.fx_rate_to_usd else 1.0

    styles = getSampleStyleSheet()

    # Custom Paragraph Styles
    style_normal = ParagraphStyle(
        "CustNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=COLOR_SECONDARY,
    )
    style_normal_muted = ParagraphStyle(
        "CustNormalMuted",
        parent=style_normal,
        fontSize=7.5,
        leading=9.5,
        textColor=COLOR_MUTED,
    )
    style_bold = ParagraphStyle(
        "CustBold",
        parent=style_normal,
        fontName="Helvetica-Bold",
    )
    style_title = ParagraphStyle(
        "CustDocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        alignment=2,  # Right-aligned
        textColor=COLOR_PRIMARY,
    )
    style_cell_center = ParagraphStyle(
        "CustCellCenter",
        parent=style_normal,
        alignment=1,
    )
    style_cell_right = ParagraphStyle(
        "CustCellRight",
        parent=style_normal,
        alignment=2,
    )
    style_cell_desc = ParagraphStyle(
        "CustCellDesc",
        parent=style_normal,
        fontSize=8,
        leading=10.5,
    )
    style_section_title = ParagraphStyle(
        "CustSectionTitle",
        parent=style_bold,
        fontSize=9,
        leading=12,
        textColor=COLOR_PRIMARY,
    )

    story = []

    # -------------------------------------------------------------------------
    # 1. Header Block (Logo Left, QUOTATION Heading Right)
    # -------------------------------------------------------------------------
    left_header_elements = [_get_logo_flowable()]
    if quote.legal_entity_name:
        left_header_elements.extend([
            Spacer(1, 3),
            Paragraph(xml_escape(quote.legal_entity_name), style_bold),
        ])
    if quote.legal_entity_address:
        left_header_elements.append(
            Paragraph(xml_escape(quote.legal_entity_address), style_normal_muted)
        )
    if quote.legal_entity_registration_number:
        left_header_elements.append(
            Paragraph(f"Reg / Tax ID: {xml_escape(quote.legal_entity_registration_number)}", style_normal_muted)
        )
    if quote.legal_entity_contact:
        left_header_elements.append(
            Paragraph(xml_escape(quote.legal_entity_contact), style_normal_muted)
        )

    header_table = Table(
        [[left_header_elements, Paragraph("QUOTATION", style_title)]],
        colWidths=[335, 188],
    )
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 8))

    # Accent Divider Line
    divider = Table([[""]], colWidths=[523], rowHeights=[1.5])
    divider.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_ACCENT),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(divider)
    story.append(Spacer(1, 8))

    # -------------------------------------------------------------------------
    # 2. Customer, Project & Quotation Reference Details Block
    # -------------------------------------------------------------------------
    date_str = (
        quote.date.strftime("%d %b %Y")
        if isinstance(quote.date, datetime)
        else str(quote.date or "")
    )

    cust_details = [
        Paragraph("<b>PREPARED FOR:</b>", style_bold),
        Spacer(1, 2),
        Paragraph(f"<b>Customer:</b> {xml_escape(quote.client_name or '')}", style_normal),
    ]
    if quote.attention:
        cust_details.append(
            Paragraph(f"<b>Attention:</b> {xml_escape(quote.attention)}", style_normal)
        )

    solution_name = quote.solution.name if quote.solution else "Custom Solution"
    proj_details = [
        Paragraph("<b>QUOTATION DETAILS:</b>", style_bold),
        Spacer(1, 2),
        Paragraph(f"<b>Quote Ref:</b> {xml_escape(quote.quote_ref_no or '')}", style_normal),
        Paragraph(f"<b>Date:</b> {xml_escape(date_str)}", style_normal),
        Paragraph(f"<b>Solution:</b> {xml_escape(solution_name)}", style_normal),
    ]
    if quote.description:
        proj_details.append(
            Paragraph(f"<b>Description:</b> {xml_escape(quote.description)}", style_normal)
        )

    meta_table = Table([[cust_details, proj_details]], colWidths=[261, 262])
    meta_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_SECTION),
            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # -------------------------------------------------------------------------
    # 3. Bill of Quantities (BOQ) Table
    # -------------------------------------------------------------------------
    col_widths = [24, 76, 225, 32, 80, 86]
    boq_data = [
        [
            Paragraph("<b>#</b>", ParagraphStyle("TH_C", parent=style_cell_center, textColor=colors.white)),
            Paragraph("<b>Part Number</b>", ParagraphStyle("TH_L", parent=style_bold, textColor=colors.white)),
            Paragraph("<b>Description</b>", ParagraphStyle("TH_D", parent=style_bold, textColor=colors.white)),
            Paragraph("<b>Qty</b>", ParagraphStyle("TH_Q", parent=style_cell_center, textColor=colors.white)),
            Paragraph(f"<b>Unit Price ({xml_escape(currency)})</b>", ParagraphStyle("TH_U", parent=style_cell_right, textColor=colors.white)),
            Paragraph(f"<b>Total ({xml_escape(currency)})</b>", ParagraphStyle("TH_T", parent=style_cell_right, textColor=colors.white)),
        ]
    ]

    table_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_BG_TH),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]

    grouped_sections = _group_line_items_by_section(quote.line_items)
    item_counter = 1
    current_row = 1

    if grouped_sections:
        for section_name, items in grouped_sections.items():
            # Section header row spanning all columns
            section_title_p = Paragraph(f"<b>{xml_escape(section_name)}</b>", style_section_title)
            boq_data.append([section_title_p, "", "", "", "", ""])
            table_styles.extend([
                ("SPAN", (0, current_row), (-1, current_row)),
                ("BACKGROUND", (0, current_row), (-1, current_row), COLOR_BG_SECTION),
                ("TOPPADDING", (0, current_row), (-1, current_row), 4),
                ("BOTTOMPADDING", (0, current_row), (-1, current_row), 4),
            ])
            current_row += 1

            for item in items:
                unit_sell_usd = Decimal(str(item.unit_sell_price_snapshot or 0))
                unit_sell_local = (unit_sell_usd / Decimal(str(fx_rate))) if fx_rate else Decimal(0)
                qty = item.quantity or 1
                line_total_local = unit_sell_local * Decimal(qty)

                part_str = item.part_number or "Custom"
                desc_p = Paragraph(xml_escape(item.description or ""), style_cell_desc)

                boq_data.append([
                    Paragraph(str(item_counter), style_cell_center),
                    Paragraph(xml_escape(part_str), style_normal),
                    desc_p,
                    Paragraph(str(qty), style_cell_center),
                    Paragraph(_format_currency(unit_sell_local, currency), style_cell_right),
                    Paragraph(_format_currency(line_total_local, currency), style_cell_right),
                ])
                item_counter += 1
                current_row += 1
    else:
        boq_data.append([
            Paragraph("No line items in this quotation.", style_normal), "", "", "", "", ""
        ])
        table_styles.append(("SPAN", (0, 1), (-1, 1)))

    boq_table = Table(boq_data, colWidths=col_widths, repeatRows=1)
    boq_table.setStyle(TableStyle(table_styles))
    story.append(boq_table)
    story.append(Spacer(1, 8))

    # -------------------------------------------------------------------------
    # 4. Financial Summary Block
    # -------------------------------------------------------------------------
    subtotal_usd = Decimal(str(quote.subtotal_sell_usd or 0))
    subtotal_local = (subtotal_usd / Decimal(str(fx_rate))) if fx_rate else Decimal(0)
    tax_amount = Decimal(str(quote.tax_amount or 0))
    total_local = Decimal(str(quote.total_sell_local or (subtotal_local + tax_amount)))

    summary_rows = [
        [
            Paragraph("<b>Subtotal:</b>", style_cell_right),
            Paragraph(_format_currency(subtotal_local, currency), style_cell_right),
        ]
    ]

    if getattr(quote, "tax_enabled", False) and tax_amount > 0:
        tax_pct = float(quote.tax_rate_percent or 0)
        summary_rows.append([
            Paragraph(f"<b>Tax ({tax_pct:.1f}%):</b>", style_cell_right),
            Paragraph(_format_currency(tax_amount, currency), style_cell_right),
        ])

    summary_rows.append([
        Paragraph(f"<b>TOTAL ({xml_escape(currency)}):</b>", ParagraphStyle("SumTotL", parent=style_bold, fontSize=10, alignment=2, textColor=COLOR_PRIMARY)),
        Paragraph(_format_currency(total_local, currency), ParagraphStyle("SumTotR", parent=style_bold, fontSize=10.5, alignment=2, textColor=COLOR_PRIMARY)),
    ])

    summary_table = Table(summary_rows, colWidths=[130, 110])
    summary_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("LINEABOVE", (0, -1), (-1, -1), 1, COLOR_BORDER_DARK),
            ("LINEBELOW", (0, -1), (-1, -1), 1.5, COLOR_PRIMARY),
            ("BACKGROUND", (0, -1), (-1, -1), COLOR_BG_SECTION),
        ])
    )

    # Wrap summary in a right-aligned container
    summary_container = Table(
        [["", summary_table]],
        colWidths=[283, 240],
    )
    summary_container.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    story.append(KeepTogether([summary_container]))

    # -------------------------------------------------------------------------
    # 5. Build Document with NumberedCanvas
    # -------------------------------------------------------------------------
    def canvas_factory(*args, **kwargs):
        c = NumberedCanvas(*args, **kwargs)
        c.quote_ref_no = quote.quote_ref_no or ""
        return c

    doc.build(story, canvasmaker=canvas_factory)
    buf.seek(0)
    return buf

