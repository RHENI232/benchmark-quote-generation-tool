"""
CP6-B Export Service — Deterministic programmatic Excel workbook generation.

Generates three export types:
  1. Customer Copy  — sell-only, region display currency
  2. Internal Copy  — cost + sell + margin, always USD
  3. Tracking Sheet  — section/brand rollups, always USD

All monetary totals use native Excel formulas (FR-31).
Product sections are separated by blank rows (FR-32).
"""
from io import BytesIO
from collections import OrderedDict
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, numbers
from openpyxl.utils import get_column_letter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _col(n: int) -> str:
    """1-based column number to Excel letter."""
    return get_column_letter(n)


def _currency_fmt(currency_code: str) -> str:
    """Return an openpyxl number format string for a given currency."""
    symbol_map = {
        "USD": "$",
        "INR": "₹",
        "SGD": "S$",
        "EUR": "€",
        "GBP": "£",
    }
    sym = symbol_map.get(currency_code, currency_code + " ")
    return f'#,##0.00 "{sym}"'


_BOLD = Font(bold=True)
_HEADER_FONT = Font(bold=True, size=12)
_PCT_FMT = '0.00%'


def _group_items_by_section(line_items):
    """Group line items by their section, preserving sort_order."""
    sections = OrderedDict()
    sorted_items = sorted(line_items, key=lambda li: (li.section or "", li.sort_order))
    for item in sorted_items:
        key = item.section or "Uncategorized"
        sections.setdefault(key, []).append(item)
    return sections


def _write_header_row(ws, row, values, font=_BOLD):
    """Write a row of bold header values."""
    for col_idx, val in enumerate(values, start=1):
        cell = ws.cell(row=row, column=col_idx, value=val)
        cell.font = font


# ---------------------------------------------------------------------------
# Customer Copy
# ---------------------------------------------------------------------------

def generate_customer_copy(quote) -> BytesIO:
    """
    Customer Copy workbook.

    Columns: Part Number | Description | Quantity | Unit Sell Price | Total Sell Price
    Formulas: Total Sell Price = Quantity * Unit Sell Price
              Grand Total = SUM(Total Sell Price column)
    Currency: quote.currency_code (region display currency)
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Quote"

    currency_code = quote.currency_code or "USD"
    fx_rate = float(quote.fx_rate_to_usd) if quote.fx_rate_to_usd else 1.0
    cur_fmt = _currency_fmt(currency_code)

    # --- Letterhead / Header ---
    row = 1
    if quote.legal_entity_name:
        ws.cell(row=row, column=1, value=quote.legal_entity_name).font = _HEADER_FONT
        row += 1
    if quote.legal_entity_address:
        ws.cell(row=row, column=1, value=quote.legal_entity_address)
        row += 1
    if quote.legal_entity_contact:
        ws.cell(row=row, column=1, value=quote.legal_entity_contact)
        row += 1
    if quote.legal_entity_registration_number:
        ws.cell(row=row, column=1, value=f"Reg: {quote.legal_entity_registration_number}")
        row += 1

    row += 1  # blank line after letterhead

    ws.cell(row=row, column=1, value="Client Name:").font = _BOLD
    ws.cell(row=row, column=2, value=quote.client_name)
    row += 1
    ws.cell(row=row, column=1, value="Quote Reference:").font = _BOLD
    ws.cell(row=row, column=2, value=quote.quote_ref_no)
    row += 1
    ws.cell(row=row, column=1, value="Date:").font = _BOLD
    ws.cell(row=row, column=2, value=quote.date.strftime("%Y-%m-%d") if quote.date else "")
    row += 1
    ws.cell(row=row, column=1, value="Currency:").font = _BOLD
    ws.cell(row=row, column=2, value=currency_code)
    row += 1

    row += 1  # blank line before table

    # --- Column Headers ---
    columns = ["Part Number", "Description", "Quantity", "Unit Sell Price", "Total Sell Price"]
    _write_header_row(ws, row, columns)
    row += 1

    # --- Line Items grouped by section ---
    sections = _group_items_by_section(quote.line_items)
    total_col_letter = _col(5)  # E
    data_rows = []  # track rows that have Total Sell Price formulas
    first_section = True

    for section_name, items in sections.items():
        # Blank separator row between sections (FR-32)
        if not first_section:
            row += 1  # blank row
        first_section = False

        # Section header
        ws.cell(row=row, column=1, value=section_name).font = _BOLD
        row += 1

        for item in items:
            ws.cell(row=row, column=1, value=item.part_number or "")
            ws.cell(row=row, column=2, value=item.description)
            ws.cell(row=row, column=3, value=item.quantity)

            # Unit Sell Price in display currency
            unit_sell_local = float(item.unit_sell_price_snapshot) / fx_rate if fx_rate != 0 else 0
            cell_unit = ws.cell(row=row, column=4, value=round(unit_sell_local, 2))
            cell_unit.number_format = cur_fmt

            # Total Sell Price = Qty * Unit Sell (formula)
            qty_ref = f"{_col(3)}{row}"
            unit_ref = f"{_col(4)}{row}"
            cell_total = ws.cell(row=row, column=5)
            cell_total.value = f"={qty_ref}*{unit_ref}"
            cell_total.number_format = cur_fmt

            data_rows.append(row)
            row += 1

    # --- Grand Total ---
    row += 1  # blank before grand total
    ws.cell(row=row, column=4, value="Grand Total:").font = _BOLD

    if data_rows:
        # Build a SUM that references only the data rows
        sum_parts = ",".join(f"{total_col_letter}{r}" for r in data_rows)
        cell_grand = ws.cell(row=row, column=5)
        cell_grand.value = f"=SUM({sum_parts})"
        cell_grand.number_format = cur_fmt
        cell_grand.font = _BOLD

    # Auto-width columns
    for col_idx in range(1, 6):
        ws.column_dimensions[_col(col_idx)].width = 18

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Internal Copy
# ---------------------------------------------------------------------------

def generate_internal_copy(quote) -> BytesIO:
    """
    Internal Copy workbook.

    Columns: Part Number | Description | Quantity | Unit Cost Price |
             Unit Sell Price | Total Cost | Total Sell | Margin %
    Currency: Always USD.
    Formulas:
      Total Cost = Qty * Unit Cost
      Total Sell = Qty * Unit Sell
      Margin %   = (Total Sell - Total Cost) / Total Sell  (guarded)
      Grand Totals = SUM(...)
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Internal"

    cur_fmt = _currency_fmt("USD")

    # --- Header ---
    row = 1
    ws.cell(row=row, column=1, value="Client Name:").font = _BOLD
    ws.cell(row=row, column=2, value=quote.client_name)
    row += 1
    ws.cell(row=row, column=1, value="Quote Reference:").font = _BOLD
    ws.cell(row=row, column=2, value=quote.quote_ref_no)
    row += 1
    ws.cell(row=row, column=1, value="Date:").font = _BOLD
    ws.cell(row=row, column=2, value=quote.date.strftime("%Y-%m-%d") if quote.date else "")
    row += 1
    ws.cell(row=row, column=1, value="Currency:").font = _BOLD
    ws.cell(row=row, column=2, value="USD")
    row += 1

    row += 1  # blank

    # --- Column Headers ---
    columns = [
        "Part Number", "Description", "Quantity",
        "Unit Cost Price", "Unit Sell Price",
        "Total Cost", "Total Sell", "Margin %"
    ]
    _write_header_row(ws, row, columns)
    row += 1

    # Column letters: A=PartNo B=Desc C=Qty D=UnitCost E=UnitSell F=TotalCost G=TotalSell H=Margin
    sections = _group_items_by_section(quote.line_items)
    data_rows = []
    first_section = True

    for section_name, items in sections.items():
        if not first_section:
            row += 1  # blank separator (FR-32)
        first_section = False

        ws.cell(row=row, column=1, value=section_name).font = _BOLD
        row += 1

        for item in items:
            ws.cell(row=row, column=1, value=item.part_number or "")
            ws.cell(row=row, column=2, value=item.description)
            ws.cell(row=row, column=3, value=item.quantity)

            cell_uc = ws.cell(row=row, column=4, value=float(item.unit_cost_price_snapshot))
            cell_uc.number_format = cur_fmt

            cell_us = ws.cell(row=row, column=5, value=float(item.unit_sell_price_snapshot))
            cell_us.number_format = cur_fmt

            # Total Cost = Qty * Unit Cost (formula)
            cell_tc = ws.cell(row=row, column=6)
            cell_tc.value = f"=C{row}*D{row}"
            cell_tc.number_format = cur_fmt

            # Total Sell = Qty * Unit Sell (formula)
            cell_ts = ws.cell(row=row, column=7)
            cell_ts.value = f"=C{row}*E{row}"
            cell_ts.number_format = cur_fmt

            # Margin % = (TotalSell - TotalCost) / TotalSell guarded
            cell_m = ws.cell(row=row, column=8)
            cell_m.value = f'=IF(G{row}=0,0,(G{row}-F{row})/G{row})'
            cell_m.number_format = _PCT_FMT

            data_rows.append(row)
            row += 1

    # --- Grand Totals ---
    row += 1
    ws.cell(row=row, column=5, value="Grand Total:").font = _BOLD

    if data_rows:
        cost_refs = ",".join(f"F{r}" for r in data_rows)
        sell_refs = ",".join(f"G{r}" for r in data_rows)

        cell_gc = ws.cell(row=row, column=6)
        cell_gc.value = f"=SUM({cost_refs})"
        cell_gc.number_format = cur_fmt
        cell_gc.font = _BOLD

        cell_gs = ws.cell(row=row, column=7)
        cell_gs.value = f"=SUM({sell_refs})"
        cell_gs.number_format = cur_fmt
        cell_gs.font = _BOLD

        # Blended Margin %
        cell_gm = ws.cell(row=row, column=8)
        cell_gm.value = f'=IF(G{row}=0,0,(G{row}-F{row})/G{row})'
        cell_gm.number_format = _PCT_FMT
        cell_gm.font = _BOLD

    for col_idx in range(1, 9):
        ws.column_dimensions[_col(col_idx)].width = 18

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Tracking Sheet
# ---------------------------------------------------------------------------

def generate_tracking_sheet(quote) -> BytesIO:
    """
    Tracking Sheet workbook.

    Rolls up cost/sell by Product Section + Brand.
    Columns: Product Section | Brand | Total Cost | Total Sell | Margin %
    Currency: Always USD.
    Formulas:
      Margin % = (Total Sell - Total Cost) / Total Sell  (guarded)
      Grand Totals = SUM(...)
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Tracking"

    cur_fmt = _currency_fmt("USD")

    # --- Header ---
    row = 1
    ws.cell(row=row, column=1, value="Quote Reference:").font = _BOLD
    ws.cell(row=row, column=2, value=quote.quote_ref_no)
    row += 1
    ws.cell(row=row, column=1, value="Date:").font = _BOLD
    ws.cell(row=row, column=2, value=quote.date.strftime("%Y-%m-%d") if quote.date else "")
    row += 1

    row += 1  # blank

    # --- Column Headers ---
    columns = ["Product Section", "Brand", "Total Cost", "Total Sell", "Margin %"]
    _write_header_row(ws, row, columns)
    row += 1

    # Build rollups: (section, brand) -> (sum_cost, sum_sell)
    rollups = OrderedDict()
    sorted_items = sorted(quote.line_items, key=lambda li: (li.section or "", li.brand or ""))
    for item in sorted_items:
        key = (item.section or "Uncategorized", item.brand or "Unbranded")
        cost = float(item.line_cost_total) if item.line_cost_total else 0
        sell = float(item.line_sell_total) if item.line_sell_total else 0
        if key in rollups:
            rollups[key] = (rollups[key][0] + cost, rollups[key][1] + sell)
        else:
            rollups[key] = (cost, sell)

    # --- Data Rows ---
    # C=TotalCost  D=TotalSell  E=Margin%
    data_rows = []
    for (section, brand), (total_cost, total_sell) in rollups.items():
        ws.cell(row=row, column=1, value=section)
        ws.cell(row=row, column=2, value=brand)

        cell_c = ws.cell(row=row, column=3, value=total_cost)
        cell_c.number_format = cur_fmt

        cell_s = ws.cell(row=row, column=4, value=total_sell)
        cell_s.number_format = cur_fmt

        # Margin % formula
        cell_m = ws.cell(row=row, column=5)
        cell_m.value = f'=IF(D{row}=0,0,(D{row}-C{row})/D{row})'
        cell_m.number_format = _PCT_FMT

        data_rows.append(row)
        row += 1

    # --- Grand Totals ---
    row += 1
    ws.cell(row=row, column=2, value="Grand Total:").font = _BOLD

    if data_rows:
        cost_refs = ",".join(f"C{r}" for r in data_rows)
        sell_refs = ",".join(f"D{r}" for r in data_rows)

        cell_gc = ws.cell(row=row, column=3)
        cell_gc.value = f"=SUM({cost_refs})"
        cell_gc.number_format = cur_fmt
        cell_gc.font = _BOLD

        cell_gs = ws.cell(row=row, column=4)
        cell_gs.value = f"=SUM({sell_refs})"
        cell_gs.number_format = cur_fmt
        cell_gs.font = _BOLD

        cell_gm = ws.cell(row=row, column=5)
        cell_gm.value = f'=IF(D{row}=0,0,(D{row}-C{row})/D{row})'
        cell_gm.number_format = _PCT_FMT
        cell_gm.font = _BOLD

    for col_idx in range(1, 6):
        ws.column_dimensions[_col(col_idx)].width = 20

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
