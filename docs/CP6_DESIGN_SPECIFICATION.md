# CP6 DESIGN SPECIFICATION: Quote Retrieval & Excel Export

## 1. Purpose
The Quote Retrieval & Excel Export checkpoint (CP-6) finalizes the backend lifecycle of a quote by enabling users to list, search, and export saved quotes to Excel. This fulfills the primary business function of replacing manual Excel quotes with system-generated spreadsheets, enabling the upcoming frontend scaffolding to rely on a fully functionally complete backend API.

## 2. Scope
CP-6 contains exactly two major capabilities:
1. **Quote List & Search:** A paginated, searchable API endpoint for retrieving saved quote headers.
2. **Quote Excel Export:** Three separate Excel workbook generation endpoints (Customer Copy, Internal Copy, Tracking Sheet) with injected formulas.

## 3. Business Requirements
These requirements are directly traceable to authoritative project documentation:
- **FR-34.1 (RBAC Visibility):** The list must allow Sales users to see only quotes they authored, while Management and Admin users see all saved quotes.
- **Quote List Data (`docs/permissions.md`):** The list must expose row number, Client Name, Region/Country, and Quote Generated Date.
- **Quote Search (`docs/permissions.md`):** The search box must match Client Name.
- **FR-29 (Export Output):** Generate three *separate* spreadsheet files:
  - **Customer Copy:** Sell price only, Region display currency, Region letterhead.
  - **Internal Copy:** Same line items + Cost Price, Total Cost, Margin %, always in USD.
  - **Tracking Sheet:** Cost totals and Sell totals rolled up by product section and brand.
- **FR-31 (Excel Formulas):** Output must contain actual Excel formulas (SUM, multiplication, margin) rather than static calculated values.
- **FR-32 (Section Spacing):** Each product section must be visually separated by a blank gap.
- **FR-33 (Export Security):** Sales-tier users must be blocked server-side from downloading Internal or Tracking copies. (Also applies to Catalog Entry tier per `docs/requirements.md`).

## 4. Implementation Decisions
The following are technical design decisions made for CP-6. They are NOT explicitly mandated by the business requirements:
- **Three Separate Endpoints:** Excel files will be delivered through three separate GET endpoints (`/export/customer`, `/export/internal`, `/export/tracking`).
- **No ZIP Packaging:** No ZIP endpoint will be implemented. (FR-29 requires three separate files, but does not specify ZIP packaging).
- **Saved Quotes Only:** Only persisted/saved quotes can be exported. Transient preview quotes are not exportable.
- **List Pagination:** The List & Search API will support technical pagination parameters (`skip`, `limit`).
- **File Naming Convention:** Filenames will use `<quote_ref_no>_Customer_Copy.xlsx`, `<quote_ref_no>_Internal.xlsx`, `<quote_ref_no>_Tracking.xlsx`.
- **Generated Workbook Structure:** Because no `.xlsx` template exists in the repository, CP-6 defines a deterministic, hardcoded programmatic workbook structure using Python (e.g., `openpyxl`).

## 5. Quote List & Search
Provides a list of saved quotes for the dashboard/history view.
- Searches by `customer_name` (case-insensitive partial match).
- Returns the specific subset of fields required by `docs/permissions.md` (Quote Reference, Client Name, Region, Date).

## 6. Quote Excel Export
Provides the final deliverable output.
- Handled dynamically on-the-fly.
- Relies on the CP-4 Pricing Engine's computed values, but replaces the static final calculation fields with native Excel formulas where applicable.

## 7. Customer Copy
- **Workbook Purpose:** The outward-facing quote given to the client.
- **Worksheets:** Single sheet (e.g., "Quote").
- **Columns:** Part Number, Description, Quantity, Unit Sell Price, Total Sell Price.
- **Header Fields:** Client Name, Quote Reference, Date. Region letterhead (NOT SPECIFIED / REQUIRES IMPLEMENTATION DECISION on exact letterhead text/logo).
- **Formulas:**
  - Total Sell Price = `Unit Sell Price * Quantity`
  - Grand Total = `SUM(Total Sell Price column)`
- **Currency Handling:** Region display currency format applied to cells.
- **Section Separation:** Blank row between product sections.
- **Totals:** Grand Total (Sell).
- **Permission Restrictions:** Downloadable by Sales, Catalog Entry, Management, Admin.
- **Filename:** `<quote_ref_no>_Customer_Copy.xlsx`

## 8. Internal Copy
- **Workbook Purpose:** The internal review document for margin and cost analysis.
- **Worksheets:** Single sheet (e.g., "Internal").
- **Columns:** Part Number, Description, Quantity, Unit Cost Price, Unit Sell Price, Total Cost, Total Sell, Margin %.
- **Header Fields:** Client Name, Quote Reference, Date.
- **Formulas:**
  - Total Cost = `Unit Cost Price * Quantity`
  - Total Sell = `Unit Sell Price * Quantity`
  - Margin % = `(Total Sell - Total Cost) / Total Sell`
  - Grand Totals = `SUM(...)`
- **Currency Handling:** Always USD.
- **Section Separation:** Blank row between product sections.
- **Totals:** Grand Total Cost, Grand Total Sell, Blended Margin %.
- **Permission Restrictions:** Management, Admin.
- **Filename:** `<quote_ref_no>_Internal.xlsx`

## 9. Tracking Sheet
- **Workbook Purpose:** High-level cost and sell rollup by section and brand.
- **Worksheets:** Single sheet (e.g., "Tracking").
- **Columns:** Product Section, Brand, Total Cost, Total Sell, Margin %.
- **Header Fields:** Quote Reference, Date.
- **Formulas:**
  - Margin % = `(Total Sell - Total Cost) / Total Sell`
  - Grand Totals = `SUM(...)`
- **Currency Handling:** Always USD.
- **Totals:** Grand Total Cost, Grand Total Sell, Blended Margin %.
- **Permission Restrictions:** Management, Admin.
- **Filename:** `<quote_ref_no>_Tracking.xlsx`

## 10. Permission Matrix
*(Note: Corrected per `docs/requirements.md` business rules - Catalog Entry tier does not have visibility into Cost/Margin and cannot download Internal/Tracking sheets).*

| Role | Customer Copy | Internal | Tracking |
|------|---------------|----------|----------|
| Sales | ALLOW | DENY | DENY |
| Catalog Entry | ALLOW | DENY | DENY |
| Management | ALLOW | ALLOW | ALLOW |
| Admin | ALLOW | ALLOW | ALLOW |

## 11. API Contracts
- `GET /api/quotes`
  - **Query Params:** `skip` (int), `limit` (int), `client_name` (str, optional)
  - **Response:** JSON array of quote summary objects.
- `GET /api/quotes/{quote_id}/export/customer`
  - **Response:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- `GET /api/quotes/{quote_id}/export/internal`
  - **Response:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- `GET /api/quotes/{quote_id}/export/tracking`
  - **Response:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

## 12. Data Requirements
The export strictly depends on the persisted Quote and QuoteLineItem rows.
Where a business field is not natively supported by the data model (e.g., specific letterhead layout), it is marked as NOT SPECIFIED / REQUIRES IMPLEMENTATION DECISION.

## 13. Formula Requirements
Excel files must use native formula syntax (e.g., `=E12*F12`) injected during generation. The generator must compute Excel row indexes dynamically based on the number of line items and blank rows inserted.

## 14. Error Handling
- **Saved quote requirement:** Endpoints require a valid `quote_id` of a persisted quote.
- **Nonexistent / Invalid quote ID:** Returns HTTP 404 Not Found.
- **Soft-deleted quote:** Returns HTTP 404 Not Found (or 403 Forbidden). (Implementation Decision).
- **Unauthorized export type:** Returns HTTP 403 Forbidden.
- **Unauthorized quote:** If a Sales user attempts to access a Quote authored by another user, returns HTTP 403 Forbidden (or 404 to obscure existence).

## 15. Security
- Sales tier cannot access Internal endpoints.
- Sales tier cannot access Tracking endpoints.
- Users cannot list or export unauthorized quotes (RBAC filtering is applied at the ORM query level).
- Deleted quotes are safely handled and inaccessible.

## 16. Dependencies
- **CP4 Requirement Engine & Pricing Engine:** Supplies the calculated BOM data.
- **CP5 Quote API:** Supplies the persistent storage layer and optimistic concurrency mechanism.
- **RBAC:** Supplies the `current_user.role_tier` for export authorization and list filtering.

## 17. Testing Strategy
**Quote List:**
- Sales visibility (only own quotes).
- Management/Admin visibility (all quotes).
- Client-name search filtering.
- Pagination limits.
- Unauthorized access (unauthenticated).

**Customer Export:**
- Correct data population.
- Correct display currency (non-USD).
- Sell-only restriction (no cost columns).
- Presence of formulas.
- Filename headers.

**Internal Export:**
- Cost, Sell, and Margin data.
- Always USD currency.
- Presence of formulas.
- Permission restrictions (Sales/Catalog Entry rejected).

**Tracking Export:**
- Section and brand rollups.
- Presence of formulas.
- Permission restrictions (Sales/Catalog Entry rejected).

**Security & Regression:**
- Ensure deleted/nonexistent quotes return 404.
- Existing CP1-CP5 tests (66/66) must continue passing.

## 18. Out of Scope
The following are explicitly excluded from CP-6:
- React frontend implementation.
- AI requirement parsing.
- Requirement Excel import/export.
- Entra ID / Microsoft 365 SSO.
- Schematic/block diagram export.
- Live FX API integration.
- Professional Services line-item picker.
- PDF export generation.
- ZIP packaging of the Excel files.

## 19. Open Questions
- **Letterhead Details:** What specific Region letterhead text/logo should be applied to the Customer Copy? (NOT SPECIFIED).
- **Excel Styling:** Are there specific font, color, or border styling requirements for the spreadsheets? (NOT SPECIFIED).
- **Soft Delete Visibility:** Should soft-deleted quotes be completely 404'd for all users, or should Admin users have a way to view them? (Implementation decision: 404 for all).

## 20. Acceptance Criteria
1. `GET /api/quotes` returns a paginated list of quotes, filtered by RBAC.
2. `GET /api/quotes` allows searching by `client_name`.
3. `GET /api/quotes/{quote_id}/export/customer` downloads a valid Excel file containing formulas and sell prices only.
4. `GET /api/quotes/{quote_id}/export/internal` downloads a valid Excel file containing cost, sell, margin, and formulas in USD.
5. `GET /api/quotes/{quote_id}/export/tracking` downloads a valid Excel file containing rollups.
6. Sales users receive HTTP 403 when attempting to download Internal or Tracking files.

## 21. Definition of Done
- Implementation complete without altering CP5 architecture.
- Full unit test coverage passing.
- No existing tests broken.
- No ZIP packaging or PDF generation implemented.
