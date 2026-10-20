# Checkpoint CP17: Quote Revision Comparison

**Date:** 2026-10-20  
**Phase:** CP17 — Quote Revision Comparison  
**Project:** Benchmark Broadcast Systems — Presales Quote Tool  
**Branch:** `main`  
**Latest Remote Commit:** `db19618e91ffdd5e9439f3651a8e40f2a33c24f1`

---

## 1. Scope & Implementation Summary

In Checkpoint CP17, a secure, read-only revision comparison service and REST API endpoints were implemented for comparing two historical snapshots belonging to the same quote.

The comparison engine satisfies all core architectural and security rules:
1. **Intra-Quote Comparison:** Compares any two existing historical revisions (`base_revision` and `target_revision`) belonging to the same quote. Cross-quote comparison attempts are strictly rejected with `404 Not Found`.
2. **Line Item Categorization:** Detects added, removed, modified, and unchanged line items using deterministic composite keys `(catalog_item_id, part_number, section)` with duplicate occurrence indexing.
3. **Comprehensive Field Diffing:** Compares quote metadata (status, client name, attention, description, region, solution, urgency), requirement payload fields, financials (sell subtotal, local total, taxes, FX rate), legal entity configuration, and line item quantities/pricing.
4. **Historical Snapshot Integrity:** Diff calculations operate entirely on stored JSON snapshots without recalculation from live catalog prices, dynamic FX rates, or current pricing rules.
5. **Role-Based Financial Confidentiality (Cost/Margin Masking):**
   - Both snapshots are processed through `mask_revision_snapshot()` before difference calculation.
   - For users lacking `cost_visibility` permission (Sales and Catalog Entry tiers), `subtotal_cost_usd` is excluded from financial changes, and all line item cost/margin fields (`unit_cost_price_snapshot`, `line_cost_total`, `margin_percent`) in `added`, `removed`, `modified`, and `unchanged` categories are returned as `None` (`null`).
   - Line items modified solely in cost/margin do not appear as modified to unauthorized callers, completely eliminating side-channel inference.
   - Callers with `cost_visibility` (Management and Admin tiers) receive full unmasked cost and margin comparison data.
6. **Quote Ownership & Access Control:**
   - Unauthenticated and inactive requests are rejected.
   - Sales-tier callers may only compare revisions of quotes they created/own.
   - Non-Sales callers (Catalog Entry, Management, Admin) can compare revisions for any non-deleted quote.
   - Soft-deleted quotes consistently return `404 Not Found: Quote not found`.
7. **Read-Only Invariant:** Comparison queries do not modify database records or create new revisions.

---

## 2. API Endpoints & Response Behavior

### A. Query Parameter Endpoint
- **Method & Path:** `GET /api/quotes/{quote_id}/revisions/compare`
- **Response Model:** `QuoteRevisionComparisonResponse`
- **Query Parameters:**
  - `base_revision` (`int`): Base revision number (aliases supported: `from_revision`, `rev_a`).
  - `target_revision` (`int`): Target revision number (aliases supported: `to_revision`, `rev_b`).
- **Status Codes:**
  - `200 OK`: Returns the structured comparison object.
  - `400 Bad Request`: When revision numbers are missing.
  - `401 Unauthorized` / `403 Forbidden`: Unauthenticated, inactive, or unauthorized callers.
  - `403 Forbidden`: Sales user querying another user's quote (`detail="Forbidden: You do not own this quote"`).
  - `404 Not Found`: Quote not found/soft-deleted, or revision number $< 1$, or revision not found under the quote.

### B. Path-Based Endpoint Alias
- **Method & Path:** `GET /api/quotes/{quote_id}/revisions/{base_revision}/compare/{target_revision}`
- **Response Model:** `QuoteRevisionComparisonResponse`
- **Behavior:** Direct path-parameter alias delegating to the comparison service with identical authorization and security rules.

### Response Schema (`QuoteRevisionComparisonResponse`)
```json
{
  "quote_id": 10,
  "quote_ref_no": "BBS-2026-001000",
  "base_revision": {
    "revision_number": 1,
    "quote_version": 1,
    "action": "INITIAL_CREATION",
    "user_id": 2,
    "user_email": "sales@benchmark.local",
    "user_role": "Sales",
    "change_reason": null,
    "created_at": "2026-10-20T14:00:00Z"
  },
  "target_revision": {
    "revision_number": 2,
    "quote_version": 2,
    "action": "EDIT",
    "user_id": 2,
    "user_email": "sales@benchmark.local",
    "user_role": "Sales",
    "change_reason": "Expanded scope to 2 engines with ingest",
    "created_at": "2026-10-20T14:05:00Z"
  },
  "has_changes": true,
  "metadata_changes": {
    "client_name": { "old": "Initial Client", "new": "Modified Client", "changed": true }
  },
  "requirement_changes": {
    "sdi_production_ingest": { "old": false, "new": true, "changed": true }
  },
  "financial_changes": {
    "subtotal_sell_usd": { "old": "12500.00", "new": "25000.00", "changed": true },
    "total_sell_local": { "old": "12500.00", "new": "25000.00", "changed": true }
  },
  "legal_entity_changes": {},
  "line_items": {
    "added": [
      {
        "catalog_item_id": 1,
        "part_number": "MT1010",
        "brand": "wTVision",
        "description": "Ingest Base Unit",
        "section": "Ingest",
        "status": "added",
        "quantity_old": null,
        "quantity_new": 1,
        "unit_sell_price_old": null,
        "unit_sell_price_new": "5000.00",
        "line_sell_total_old": null,
        "line_sell_total_new": "5000.00",
        "unit_cost_price_old": null,
        "unit_cost_price_new": null,
        "line_cost_total_old": null,
        "line_cost_total_new": null,
        "margin_percent_old": null,
        "margin_percent_new": null,
        "field_changes": {}
      }
    ],
    "removed": [],
    "modified": [
      {
        "catalog_item_id": 19,
        "part_number": "R30001",
        "brand": "wTVision",
        "description": "Graphics Engine (Base)",
        "section": "Graphics Engine",
        "status": "modified",
        "quantity_old": 1,
        "quantity_new": 2,
        "unit_sell_price_old": "12500.00",
        "unit_sell_price_new": "12500.00",
        "line_sell_total_old": "12500.00",
        "line_sell_total_new": "25000.00",
        "unit_cost_price_old": null,
        "unit_cost_price_new": null,
        "line_cost_total_old": null,
        "line_cost_total_new": null,
        "margin_percent_old": null,
        "margin_percent_new": null,
        "field_changes": {
          "quantity": { "old": 1, "new": 2, "changed": true },
          "line_sell_total": { "old": "12500.00", "new": "25000.00", "changed": true }
        }
      }
    ],
    "unchanged": [],
    "total_added": 1,
    "total_removed": 0,
    "total_modified": 1,
    "total_unchanged": 0
  }
}
```

---

## 3. Files Changed

### Modified Files
1. [`backend/app/schemas/quote.py`](file:///C:/Users/Benchmark_Broadcast/Downloads/benchmark-quote-generation-tool/backend/app/schemas/quote.py)
   - Added `RevisionSummary`, `FieldDifference`, `LineItemDifference`, `LineItemsComparison`, and `QuoteRevisionComparisonResponse`.
2. [`backend/app/services/revision_service.py`](file:///C:/Users/Benchmark_Broadcast/Downloads/benchmark-quote-generation-tool/backend/app/services/revision_service.py)
   - Implemented `compare_quote_revisions(db, quote_id, base_revision_number, target_revision_number, current_user)`: Compares two revisions with role-based masking, duplicate occurrence indexing, and deterministic categorization.
3. [`backend/app/api/routers/quotes.py`](file:///C:/Users/Benchmark_Broadcast/Downloads/benchmark-quote-generation-tool/backend/app/api/routers/quotes.py)
   - Registered `GET /{quote_id}/revisions/compare` and `GET /{quote_id}/revisions/{base_revision}/compare/{target_revision}`.
   - Enforced route order precedence so `/compare` takes priority over integer path parameters.

### New Test Files
1. [`backend/tests/test_quote_revision_comparison.py`](file:///C:/Users/Benchmark_Broadcast/Downloads/benchmark-quote-generation-tool/backend/tests/test_quote_revision_comparison.py)
   - 17 comprehensive tests covering identical comparison, additions, removals, modifications, metadata/requirement changes, financial differences, multi-role cost masking, ownership enforcement, error handling, cross-quote rejections, routing aliases, and read-only invariants.

---

## 4. Tests Executed & Exact Results

All database tests were executed exclusively against `benchmark_test_db`. Zero tests touched the development database.

### Focused CP17 Comparison Tests
Command:
```powershell
$env:PYTHONPATH="."; .\backend\.venv\Scripts\pytest.exe backend/tests/test_quote_revision_comparison.py -v
```
Output:
```text
backend/tests/test_quote_revision_comparison.py::test_compare_identical_revisions PASSED [  5%]
backend/tests/test_quote_revision_comparison.py::test_compare_line_items_added_and_modified PASSED [ 11%]
backend/tests/test_quote_revision_comparison.py::test_compare_line_items_removed_in_reverse_comparison PASSED [ 17%]
backend/tests/test_quote_revision_comparison.py::test_compare_metadata_and_requirements PASSED [ 23%]
backend/tests/test_quote_revision_comparison.py::test_compare_status_change_metadata PASSED [ 29%]
backend/tests/test_quote_revision_comparison.py::test_cost_masking_for_sales_and_catalog_entry_comparison PASSED [ 35%]
backend/tests/test_quote_revision_comparison.py::test_cost_visibility_for_management_and_admin_comparison PASSED [ 41%]
backend/tests/test_quote_revision_comparison.py::test_sales_user_cannot_compare_other_users_quote_revisions PASSED [ 47%]
backend/tests/test_quote_revision_comparison.py::test_non_sales_roles_can_compare_any_quote_revisions PASSED [ 52%]
backend/tests/test_quote_revision_comparison.py::test_unauthenticated_and_disabled_users_blocked_from_comparison PASSED [ 58%]
backend/tests/test_quote_revision_comparison.py::test_nonexistent_quote_returns_404 PASSED [ 64%]
backend/tests/test_quote_revision_comparison.py::test_nonexistent_revision_returns_404 PASSED [ 70%]
backend/tests/test_quote_revision_comparison.py::test_missing_query_parameters_returns_400 PASSED [ 76%]
backend/tests/test_quote_revision_comparison.py::test_cross_quote_revision_comparison_rejected PASSED [ 82%]
backend/tests/test_quote_revision_comparison.py::test_soft_deleted_quote_comparison_returns_404 PASSED [ 88%]
backend/tests/test_quote_revision_comparison.py::test_query_param_aliases_and_path_route PASSED [ 94%]
backend/tests/test_quote_revision_comparison.py::test_comparison_does_not_mutate_quote_or_revision_records PASSED [100%]

====================== 17 passed, 499 warnings in 2.90s =======================
```

### Cumulative Revision Test Suites (CP14 + CP15 + CP16 + CP17)
Command:
```powershell
$env:PYTHONPATH="."; .\backend\.venv\Scripts\pytest.exe backend/tests/test_quote_revisions.py backend/tests/test_quote_revision_capture.py backend/tests/test_quote_revision_retrieval.py backend/tests/test_quote_revision_comparison.py
```
Output:
```text
collected 66 items
backend\tests\test_quote_revisions.py ................                   [ 24%]
backend\tests\test_quote_revision_capture.py ............                [ 42%]
backend\tests\test_quote_revision_retrieval.py .....................     [ 74%]
backend\tests\test_quote_revision_comparison.py .................        [100%]
====================== 66 passed, 1286 warnings in 6.94s ======================
```

### Full Application Regression Suite
- `backend/tests/test_quotes.py`: **61/61 passed**
- `backend/tests/test_fx_management.py`: **18/18 passed**
- `backend/tests/test_rbac.py`: **4/4 passed**
- `backend/tests/test_users.py`: **15/15 passed**
- `backend/tests/test_pricing_engine.py`: **9/9 passed**
- **Grand Total Across All Test Suites:** **173/173 passed, 0 failed**

---

## 5. Migration & Database Status

- **Alembic Migration Required?** **NO.** Revision comparison operates entirely on existing snapshot data.
- **Repository Alembic Head:** `e6a7b8c9d0f1 (head)` (CP14).
- **Development Database (`benchmark_quote_generation_tool`):**
  - Current Alembic revision: `d4e5f6a7b8c9` (CP13 head).
  - Quote count: 26 records preserved.
  - Table `quote_revisions`: Does not exist.
  - Confirmed 100% untouched.

---

## 6. Known Limitations

1. **Restoration Endpoint:** Restoring an earlier revision by creating a new revision snapshot is deliberately out of scope for CP17.
2. **Frontend UI Integration:** Visual comparison diff screens and side-by-side inspection widgets will be implemented in subsequent frontend checkpoints.

---

## 7. Git & Working Tree Status

```text
## main...origin/main
 M backend/app/api/routers/quotes.py
 M backend/app/schemas/quote.py
 M backend/app/services/revision_service.py
?? backend/tests/test_quote_revision_comparison.py
?? backend/tests/test_quote_revision_retrieval.py
?? current-status.txt
?? current-untracked.txt
?? docs/CP12_SMTP_INVITATION_CHECKPOINT.md
?? docs/CP16_HISTORICAL_REVISION_RETRIEVAL_CHECKPOINT.md
?? docs/CP17_QUOTE_REVISION_COMPARISON_CHECKPOINT.md
?? docs/END_TO_END_TEST_PLAN.md
?? docs/PROJECT_CHECKPOINT_2026-10-12.md
?? docs/TEST_EXECUTION_REPORT.md
?? scratch/
```

- **Confirmation:** No commits, pushes, or branch changes have occurred. All pre-existing untracked files remain intact.

