# CP-5 DESIGN SPECIFICATION: Quote Generation API (FINAL)

## 1. Purpose
The Quote Generation API (CP-5) provides the orchestration layer connecting the CP-4 engines (Requirement and Pricing) to the clients. It standardizes quote lifecycle management (creation, recalculation, saving) via secure HTTP endpoints, ensuring strict validation, optimistic concurrency, and preservation of CP-4 snapshot architecture.

## 2. Current CP-4 Baseline
- **Requirement Engine:** Implemented and tested. Validates JSON and generates abstract `BOMLineSpec` arrays.
- **Pricing Engine:** Implemented and tested. Translates abstract BOMs to concrete `QuoteLineItem` records via `lookup_key`, computing margins, FX, and taxes, strictly in `Decimal` format.
- **Models:** `Quote` and `QuoteLineItem` feature immutable snapshot columns (`unit_sell_price_snapshot`, `fx_rate_to_usd`, etc.).

## 3. CP-5 Scope
- HTTP routing and Controller layer for quotes.
- API request/response schema modeling via Pydantic.
- Secure lifecycle orchestration: Create (DRAFT), Recalculate (DRAFT), Save (SAVED), Retrieve, List, and Soft Delete.
- Integration of RBAC to enforce quote ownership and visibility constraints.
- Transactional safety for database operations.

## 4. Non-Goals
- Duplicating any business logic handled by Requirement Engine or Pricing Engine.
- Allowing clients to directly dictate prices, margin percentages, or lookup keys.
- Changing the catalog resolution architecture.
- Designing or implementing document generation (e.g., PDF/Excel exports).

## 5. Architecture
```text
Client -> FastAPI Router -> Quote Service -> Requirement Engine -> Pricing Engine -> Database
```

## 6. API Endpoint Inventory
| Method | URL | Purpose | Auth / Role |
|---|---|---|---|
| POST | `/api/quotes/preview` | Stateless engine execution | Authenticated (Any) |
| POST | `/api/quotes` | Create quote (DRAFT) | Authenticated (Any) |
| GET | `/api/quotes` | List active quotes | Authenticated (Scoped) |
| GET | `/api/quotes/{id}` | Retrieve active quote | Authenticated (Scoped) |
| PUT | `/api/quotes/{id}` | Edit quote headers | Authenticated (Quote Owner/Admin) |
| POST | `/api/quotes/{id}/recalculate` | Update pricing (DRAFT) | Authenticated (Quote Owner/Admin) |
| POST | `/api/quotes/{id}/save` | Lock quote (SAVED) | Authenticated (Quote Owner/Admin) |
| POST | `/api/quotes/{id}/duplicate` | Copy requirement to new quote | Authenticated (Any) |
| DELETE | `/api/quotes/{id}` | Soft delete quote | Authenticated (Quote Owner/Admin) |

## 7. Quote Creation Flow
1. **Submit:** Client POSTs `solution_id`, `region_id`, headers, and `requirement_data` to `/api/quotes`.
2. **Validation:** Pydantic schema validates the HTTP payload.
3. **Transaction Begin:** Quote Service opens a DB transaction.
4. **Resolution:** Service fetches `Solution` and `Region`. (404 if missing).
5. **Reference Generation:** A unique `quote_ref_no` is generated via database sequence in the format `BBS-YYYY-NNNNNN`.
6. **Requirement Engine:** Service passes `requirement_data` to `RequirementEngine`, receiving a `BOMLineSpec` array.
7. **Quote Initialization:** Service creates a `Quote` instance with user ID, `DRAFT` status, and `version = 1`.
8. **Pricing Engine:** Service invokes `PricingEngine.calculate_and_save_quote(...)`. This fetches catalog items via `lookup_key`, generates `QuoteLineItem`s, computes `Decimal` financials, and snapshots the data.
9. **Commit:** Transaction commits to the database.
10. **Return:** API returns serialized quote (stripping cost/margin if role < Management).

## 8. Draft Quote Lifecycle
`DRAFT` quotes represent active work.
- **Recalculation:** Client issues `POST /api/quotes/{id}/recalculate` with updated `requirement_data` and REQUIRED `expected_version`.
- **Behavior:** The Quote Service verifies the quote is `DRAFT`, ownership constraints, and optimistic versioning. It replaces the `requirement_data`, invokes both Engines, clears old line items, creates new line items, and increments `Quote.version`. No historical draft states are retained.

## 9. Saved Quote Lifecycle
`SAVED` quotes represent finalized, immutable historical records.
- **Transition:** Client issues `POST /api/quotes/{id}/save` with `expected_version`. Service updates status to `SAVED` and commits.
- **Immutability:** 
  - `POST /recalculate` returns HTTP 409 Conflict.
  - `PUT /api/quotes/{id}` returns HTTP 409 Conflict.
- **Duplication:** A SAVED quote can be cloned via `POST /duplicate` to form a new, unlinked `DRAFT` with `version = 1`.

## 10. Quote Deletion (Soft Delete)
- **Operation:** `DELETE /api/quotes/{id}` marks the `deleted_at` timestamp. It does NOT physically delete the database row or cascade to `QuoteLineItem`.
- **State Check:** Both DRAFT and SAVED quotes can be soft deleted.
- **RBAC:** Only the quote owner or an Admin can soft delete a quote.
- **Filtering:** Any API listing (`GET /api/quotes`) or retrieval (`GET /api/quotes/{id}`) MUST filter out records where `deleted_at IS NOT NULL` (returning 404 for deleted quotes).

## 11. Authentication and RBAC
- **Authentication:** Required for all endpoints via JWT dependencies.
- **Mutation (Edit/Recalculate/Save/Delete):** Only the Quote Owner (or an Admin) can mutate a quote.
- **Visibility (Retrieval & Listing):**
  - **Sales Tier:** Can only view/list active quotes where `created_by_user_id == current_user.id`.
  - **Catalog Entry, Management, Admin:** Can view/list *all* active quotes across the system.
- **Cost/Margin Masking:** The API must strip `line_cost_total`, `unit_cost_price_snapshot`, `margin_percent`, and `subtotal_cost_usd` if the requesting user's tier is `< Management`.

## 12. Request Schemas
**Input Schemas (Client to Server)**
- `QuoteCreate`: `solution_id`, `region_id`, `client_name`, `requirement_data: dict` (Raw JSON validated by engine).
- `QuoteRecalculate`:
  - `requirement_data: dict`
  - `expected_version: int` (REQUIRED)
- `QuoteUpdateHeaders`:
  - `client_name: Optional[str]`, `description: Optional[str]`, `attention: Optional[str]`
  - `expected_version: int` (REQUIRED)
- `QuoteSaveAction`:
  - `expected_version: int` (REQUIRED)
- `QuoteDeleteAction` (or passed as query parameter):
  - `expected_version: int` (REQUIRED)

*Clients cannot supply prices, margins, or catalog IDs.*

## 13. Response Schemas & Decimal Serialization
**Decimal API Serialization MUST strictly output JSON strings to preserve CP-4 precision guarantees.** Do NOT use JSON floating-point numbers.

Example required output format:
```json
{
  "subtotal_sell_usd": "12345.67",
  "tax_amount": "1234.57",
  "total_sell_local": "13680.24"
}
```
**Architecture:** 
- Internal Python type: `Decimal`
- Database type: `NUMERIC`
- API JSON representation: `string` (FastAPI/Pydantic models MUST be explicitly configured via `ConfigDict(json_encoders={Decimal: str})` or equivalent to serialize Decimals as strings).

**Output Schemas**
- `QuoteResponse`: Header data (ID, status, version, currency, fx_rate, totals).
- `QuoteLineItemResponse`: `description`, `quantity`, `unit_sell_price_snapshot`, `line_sell_total`, `section`.
- *Masking logic:* Handled in the router/service. User Tier < Management receives a Customer Copy variant.

## 14. Concurrency / Versioning
Optimistic concurrency is **REQUIRED** for all quote mutations (`PUT`, `POST /recalculate`, `POST /save`, `DELETE`).
- **Behavior:** The API compares the `expected_version` provided by the client with the DB `Quote.version`. 
- **Match:** The transaction proceeds, and `Quote.version` is incremented.
- **Mismatch (or Missing):** The API immediately rolls back any pending transaction and returns `409 Conflict`.
- **Error Code:** `QUOTE_VERSION_MISMATCH`
- **Recovery:** The API instructs the client to retrieve the latest quote state before retrying. 
- **Simultaneous Requests:** If two users try to SAVE simultaneously, the first increments the version, causing the second to gracefully fail with `409 Version Mismatch`.

## 15. Error Contract
Consistent JSON format:
```json
{
  "error": {
    "code": "QUOTE_VERSION_MISMATCH",
    "message": "The quote has been modified by another process. Please refresh and try again.",
    "details": {"current_version": 4, "expected_version": 3}
  }
}
```
**Mappings:**
- `400 Bad Request`: General malformed JSON or missing required fields (like `expected_version`).
- `401 Unauthorized`: Missing/invalid token.
- `403 Forbidden`: Cross-user access attempt by Sales, or unauthorized edit/delete.
- `404 Not Found`: Solution, Region, Quote ID missing, or Quote is Soft Deleted.
- `409 Conflict`: Business rule violations (`PricingEngineError`, SAVED mutation, `QUOTE_VERSION_MISMATCH`).
- `422 Unprocessable Entity`: Validation failures in Pydantic models (e.g., `RequirementPayload` validation).

## 16. Transaction Boundaries
```text
BEGIN TRANSACTION (SessionLocal)
  Fetch Quote & Region
  Verify expected_version == quote.version (409 on failure)
  Engine processing (Python-only)
  DB writes (quote.line_items flush)
  Commit OR Rollback
```
**Safety:** Because `calculate_and_save_quote` in `PricingEngine` flushes to the database but does not commit, the router/service must execute it within a `db.commit()` wrapping block, issuing `db.rollback()` on any Exception (including HTTP exceptions) to ensure no partial quotes or orphaned line items are left behind.

## 17. Security Model
- **IDOR Protection:** The API checks `quote.created_by_user_id == current_user.id` for Sales-tier users on every operation.
- **Financial Integrity:** The API does not accept financial overrides.
- **Mass Assignment:** Input schemas explicitly restrict updatable fields. `status`, `version`, `quote_ref_no`, and `deleted_at` are entirely server-controlled.

## 18. Database Impact
**An Alembic migration MUST be created during CP-5 implementation:**
1. **Quote Reference Sequence:** Create a global PostgreSQL `SEQUENCE` (e.g., `quote_ref_seq`). 
   - *Concurrency Safety:* Because `nextval()` is atomic and outside transaction rollbacks, simultaneous requests (e.g., Request A and B) are guaranteed to receive unique sequence numbers (e.g., 127 and 128).
   - *Year Interaction:* The reference is formatted dynamically at insertion as `BBS-YYYY-NNNNNN` where `YYYY` is the current year and `NNNNNN` is `nextval()`. The sequence is non-gapless and operates globally (does not reset to zero at the new year). Thus, `BBS-2026-000127` followed by `BBS-2027-000128` is perfectly safe, uniquely formatted, and concurrency-proof regardless of worker restarts.
2. **Soft Delete Column:** Add `deleted_at = Column(DateTime, nullable=True, index=True)` to the `quotes` table to support FR-34 exclusion filtering.

## 19. API/Engine Responsibility Matrix
| Responsibility | API Layer (CP-5) | Requirement Engine (CP-4) | Pricing Engine (CP-4) | Database |
|---|---|---|---|---|
| Validate API request shape (HTTP) | YES | | | |
| Business requirement rules | | YES | | |
| BOM generation | | YES | | |
| Catalog lookup | | | YES | |
| Sell/cost calculation & FX | | | YES | |
| Quote DB persistence & Transaction | YES (Service) | | | YES |
| Authentication & Authorization | YES | | | |

## 20. Testing Strategy
- **Unit Tests:** Decimal Serialization (string output), Response serialization (cost masking logic).
- **Integration Tests:** 
  - `test_create_quote_success` (verifies `quote_ref_no` generation)
  - `test_soft_delete_quote` (verifies exclusion from lists and 404 on GET)
  - `test_concurrency_version_mismatch_409` (verifies rollback and error structure)
  - `test_save_quote_mutates_status`
- All 57 previous tests must remain functional.

## 21. Observability
- **Log Events:** `quote_created`, `quote_recalculated`, `quote_saved`, `quote_deleted`, `concurrency_conflict`, `engine_failure`.
- **Sensitive Data:** Exclude `requirement_data` payload from standard INFO logs.

## 22. Adversarial Review
### BLOCKING
- *None.*

### HIGH
- *None.*

### MEDIUM
- *None.* (Duplicate POST requests for Quote Creation will safely produce two distinct quotes due to the concurrency-safe `quote_ref_no` sequence design. Soft deletes ensure no historical audit loss.)

### LOW
- *FX Failure:* If the external FX API fails and no cached rate exists, `PricingEngineError` halts the transaction. Client receives a `409/422`, requiring Admin intervention. Acceptable per FR-26.

### NO ISSUE (Confirmed Safe)
- **IDOR/Ownership:** Checked explicitly on all mutations, retrievals, and deletions.
- **RBAC Masking:** Handled structurally in API response schemas.
- **SAVED Immutability:** Blocked actively at the controller level for any structural modifications.
- **DRAFT Recalculation:** `expected_version` is explicitly REQUIRED.
- **Decimal Precision:** Hardcoded to JSON `string`.
- **Transaction Rollback:** Enforced explicitly by API route handlers.

## 23. Implementation Plan
- **Phase 1:** Alembic Migration (Add `deleted_at` and `quote_ref_seq`).
- **Phase 2:** API Schemas (Decimals as Strings, Concurrency fields, Cost-masking).
- **Phase 3:** Quote Orchestration Service (Sequence fetching, Transaction & RBAC handling).
- **Phase 4:** API Endpoints & Exception Handlers.
- **Phase 5:** Integration & RBAC tests.

## 24. Final Status

# HUMAN APPROVAL CHECKPOINT

CP-5 Design Specification has been revised after adversarial review.

The following issues have been explicitly addressed:
- FR-34 quote deletion
- Optimistic concurrency
- Decimal API serialization
- `quote_ref_no` handling

No CP-5 application code has been implemented.

No database migrations have been created.

No tests have been modified or added.

No configuration has been changed.

No commit has been created.

No push has been performed.

**WAITING FOR HUMAN APPROVAL BEFORE CP-5 IMPLEMENTATION.**
