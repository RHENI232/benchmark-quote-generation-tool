# Checkpoint CP16: Historical Quote Revision Retrieval API

**Date:** 2026-10-20  
**Phase:** CP16 — Historical Quote Revision Retrieval API  
**Project:** Benchmark Broadcast Systems — Presales Quote Tool  
**Branch:** `main`  
**Latest Remote Commit:** `db19618e91ffdd5e9439f3651a8e40f2a33c24f1`

---

## 1. Scope & Implementation Summary

In Checkpoint CP16, read-only REST API endpoints were implemented for retrieving the immutable historical quote revision history and individual revision snapshots created in CP14 and CP15.

The implementation strictly satisfies the following core architecture and security principles:
1. **Read-Only Operation:** Retrieval endpoints perform purely read-only queries. They make zero mutations to `Quote` or `QuoteRevision` records and do not alter quote versions or audit logs.
2. **Deterministic Ordering:** Revision history defaults to chronological order (`revision_number.asc()`), with optional reverse chronological order (`order=desc`).
3. **Bounded Pagination:** Revisions list pagination supports `skip` (offset $\ge 0$) and `limit` ($1 \le \text{limit} \le 100$, default 50). Out-of-range inputs (e.g., negative skip or non-positive limit) return clear validation errors (`400 Bad Request` or `422 Unprocessable Entity`), and values $> 100$ are safely clamped to 100.
4. **Role-Based Financial Confidentiality:** Built-in server-side masking guarantees that callers without `cost_visibility` permission (Sales and Catalog Entry tiers) receive `None` for all sensitive financial figures (`subtotal_cost_usd`, and line item `unit_cost_price_snapshot`, `line_cost_total`, `margin_percent`). Sell prices, taxes, quantities, descriptions, and FX rates remain visible. Callers with `cost_visibility` (Management and Admin tiers) receive full unmasked financial snapshots.
5. **Ownership & Access Enforcement:** Sales-tier users may only retrieve revisions for quotes they own (`quote.created_by_user_id == current_user.id`). Other roles (Catalog Entry, Management, Admin) can access any non-deleted quote.
6. **Strict Snapshot Integrity:** Historical snapshots are returned exactly as stored in the database at the time the revision was created. No recalculation against current catalog prices, live regional FX rates, tax rules, or solution requirements is performed.
7. **Cross-Quote Isolation & 404 Consistency:** Inaccessible or missing quotes return `404 Quote not found`. Nonexistent revision numbers or cross-quote revision access attempts return `404 Revision not found`.

---

## 2. Endpoints & Response Behavior

### A. List Quote Revisions
- **Method & Path:** `GET /api/quotes/{quote_id}/revisions`
- **Response Model:** `List[QuoteRevisionResponse]`
- **Query Parameters:**
  - `skip` (`int`, default `0`): Offset for pagination. Must be $\ge 0$.
  - `limit` (`int`, default `50`): Maximum items per page. Must be $\ge 1$. Clamped to $100$ if $> 100$.
  - `order` (`str`, default `"asc"`): Ordering direction. Options: `"asc"` (Revision 1 -> 2 -> ...), `"desc"` (Revision N -> N-1 -> ...).
- **Status Codes:**
  - `200 OK`: Returns the list of historical revision objects.
  - `400 Bad Request`: When `skip < 0`, `limit < 1`, or `order` is not `"asc"` / `"desc"`.
  - `401 Unauthorized` / `403 Forbidden`: Unauthenticated, inactive, or unauthorized requests.
  - `403 Forbidden`: Sales user requesting a quote owned by another user (`detail="Forbidden: You do not own this quote"`).
  - `404 Not Found`: Parent quote does not exist or is soft-deleted (`detail="Quote not found"`).
  - `422 Unprocessable Entity`: Malformed non-integer query parameter types.

### B. Get Specific Revision Snapshot
- **Method & Path:** `GET /api/quotes/{quote_id}/revisions/{revision_number}`
- **Response Model:** `QuoteRevisionResponse`
- **Path Parameters:**
  - `quote_id` (`int`): Parent quote ID.
  - `revision_number` (`int`): Sequential revision number (1-based index).
- **Status Codes:**
  - `200 OK`: Returns the exact historical revision snapshot and capturing metadata.
  - `401 Unauthorized` / `403 Forbidden`: Unauthenticated, inactive, or unauthorized requests.
  - `403 Forbidden`: Sales user requesting a revision of a quote owned by another user.
  - `404 Not Found`: Parent quote does not exist or is soft-deleted (`detail="Quote not found"`), or the requested `revision_number` does not exist under this quote (`detail="Revision not found"`).

### Response Schema (`QuoteRevisionResponse`)
```json
{
  "id": 1,
  "quote_id": 10,
  "revision_number": 1,
  "quote_version": 1,
  "action": "INITIAL_CREATION",
  "user_id": 2,
  "user_email": "sales@benchmark.local",
  "user_role": "Sales",
  "change_reason": null,
  "created_at": "2026-10-20T14:00:00Z",
  "snapshot_data": {
    "schema_version": "1.0",
    "captured_at": "2026-10-20T14:00:00Z",
    "quote": { ... },
    "financials": {
      "currency_code": "USD",
      "fx_rate_to_usd": "1.000000",
      "fx_rate_as_of": "2026-10-16 12:00:00 UTC",
      "tax_enabled": false,
      "tax_rate_percent": null,
      "subtotal_cost_usd": null,
      "subtotal_sell_usd": "12500.00",
      "tax_amount": "0.00",
      "total_sell_local": "12500.00"
    },
    "legal_entity": { ... },
    "line_items": [
      {
        "id": 101,
        "catalog_item_id": 5,
        "sort_order": 0,
        "section": "Core Equipment",
        "part_number": "MT1010",
        "brand": "wTVision",
        "description": "Ingest Base Unit",
        "quantity": 1,
        "unit_cost_price_snapshot": null,
        "unit_sell_price_snapshot": "5000.00",
        "line_cost_total": null,
        "line_sell_total": "5000.00",
        "margin_percent": null
      }
    ]
  }
}
```

---

## 3. Authorization & Cost-Masking Rules

| Role Tier | Quote Ownership Check | Can Access Any Quote History? | Cost & Margin Visible in Snapshot? |
| :--- | :---: | :---: | :---: |
| **Sales** | Yes (own quotes only) | No (403 for non-owned) | **No** (`subtotal_cost_usd`, line costs, and margins masked to `None`) |
| **Catalog Entry** | No (global read) | Yes | **No** (Catalog Entry has no quote cost visibility) |
| **Management** | No (global read) | Yes | **Yes** (unmasked exact historical values) |
| **Admin** | No (global read) | Yes | **Yes** (unmasked exact historical values) |

Masking implementation:
- Handled via `mask_revision_snapshot()` in `backend/app/services/revision_service.py`.
- Evaluates `has_permission("cost_visibility", current_user)`.
- Operates on a deep-copied dictionary structure, completely isolating the in-memory response data from SQLAlchemy's session and ORM models to prevent accidental state dirtying or trigger violations.

---

## 4. Files Changed

### Modified Files
1. [`backend/app/services/revision_service.py`](file:///C:/Users/Benchmark_Broadcast/Downloads/benchmark-quote-generation-tool/backend/app/services/revision_service.py)
   - Added `mask_revision_snapshot(snapshot, current_user)`: Applies deep-copy role-based financial masking.
   - Added `get_quote_revisions(db, quote_id, skip, limit, order)`: Fetches paginated revisions with deterministic ordering and eager-loaded user relationship (`joinedload`).
   - Added `get_quote_revision_by_number(db, quote_id, revision_number)`: Retrieves specific revision with eager-loaded user.
2. [`backend/app/api/routers/quotes.py`](file:///C:/Users/Benchmark_Broadcast/Downloads/benchmark-quote-generation-tool/backend/app/api/routers/quotes.py)
   - Imported `QuoteRevisionResponse`, `get_quote_revisions`, `get_quote_revision_by_number`, and `mask_revision_snapshot`.
   - Implemented `GET /{quote_id}/revisions` (`list_quote_revisions`).
   - Implemented `GET /{quote_id}/revisions/{revision_number}` (`get_quote_revision`).

### New Test Files
1. [`backend/tests/test_quote_revision_retrieval.py`](file:///C:/Users/Benchmark_Broadcast/Downloads/benchmark-quote-generation-tool/backend/tests/test_quote_revision_retrieval.py)
   - 21 focused integration tests covering revision list ordering, bounded pagination, invalid query inputs, specific revision lookup, 404 consistency, permission enforcement, multi-role cost masking, cross-quote access prevention, snapshot immutability, and read-only behavior.

---

## 5. Tests Executed & Exact Results

All database tests were executed exclusively against `benchmark_test_db`. Zero tests were pointed at the development database.

### Focused CP16 Retrieval Tests
Command:
```powershell
$env:PYTHONPATH="."; .\backend\.venv\Scripts\pytest.exe backend/tests/test_quote_revision_retrieval.py -v
```
Output:
```text
backend/tests/test_quote_revision_retrieval.py::test_revision_list_default_ordering_asc PASSED
backend/tests/test_quote_revision_retrieval.py::test_revision_list_explicit_ordering_desc PASSED
backend/tests/test_quote_revision_retrieval.py::test_revision_list_invalid_order_param PASSED
backend/tests/test_quote_revision_retrieval.py::test_revision_list_pagination_limit PASSED
backend/tests/test_quote_revision_retrieval.py::test_revision_list_pagination_skip_and_limit PASSED
backend/tests/test_quote_revision_retrieval.py::test_revision_list_pagination_clamping PASSED
backend/tests/test_quote_revision_retrieval.py::test_revision_list_invalid_pagination_inputs PASSED
backend/tests/test_quote_revision_retrieval.py::test_get_specific_revision PASSED
backend/tests/test_quote_revision_retrieval.py::test_nonexistent_quote_returns_404 PASSED
backend/tests/test_quote_revision_retrieval.py::test_nonexistent_revision_returns_404 PASSED
backend/tests/test_quote_revision_retrieval.py::test_soft_deleted_quote_returns_404 PASSED
backend/tests/test_quote_revision_retrieval.py::test_unauthenticated_requests_blocked PASSED
backend/tests/test_quote_revision_retrieval.py::test_disabled_user_blocked PASSED
backend/tests/test_quote_revision_retrieval.py::test_sales_user_cannot_access_other_users_quote_revisions PASSED
backend/tests/test_quote_revision_retrieval.py::test_non_sales_roles_can_access_any_quote_revisions PASSED
backend/tests/test_quote_revision_retrieval.py::test_cost_masking_for_sales_and_catalog_entry PASSED
backend/tests/test_quote_revision_retrieval.py::test_cost_visibility_for_management_and_admin PASSED
backend/tests/test_quote_revision_retrieval.py::test_cross_quote_revision_access_prevented PASSED
backend/tests/test_quote_revision_retrieval.py::test_historical_snapshot_values_unaffected_by_subsequent_quote_edits PASSED
backend/tests/test_quote_revision_retrieval.py::test_retrieval_does_not_mutate_quote_or_revision_records PASSED
backend/tests/test_quote_revision_retrieval.py::test_compatibility_with_existing_quote_endpoints PASSED

====================== 21 passed, 606 warnings in 3.27s =======================
```

### Cumulative Revision Test Suites (CP14 + CP15 + CP16)
Command:
```powershell
$env:PYTHONPATH="."; .\backend\.venv\Scripts\pytest.exe backend/tests/test_quote_revisions.py backend/tests/test_quote_revision_capture.py backend/tests/test_quote_revision_retrieval.py
```
Output:
```text
collected 49 items
backend\tests\test_quote_revisions.py ................                   [ 32%]
backend\tests\test_quote_revision_capture.py ............                [ 57%]
backend\tests\test_quote_revision_retrieval.py .....................     [100%]
====================== 49 passed, 891 warnings in 4.53s =======================
```

### Regression Suites
- `backend/tests/test_quotes.py`: **61/61 passed**
- `backend/tests/test_fx_management.py`: **18/18 passed**
- `backend/tests/test_rbac.py`: **4/4 passed**
- `backend/tests/test_users.py`: **15/15 passed**
- `backend/tests/test_pricing_engine.py`: **9/9 passed**
- **Total Passing Tests Verified:** **156/156 passed**

---

## 6. Migration and Database Status

- **Alembic Head:** `e6a7b8c9d0f1 (head)` — CP14 Quote Revisions table.
- **Development Database (`benchmark_quote_generation_tool`):**
  - Current Alembic version: `d4e5f6a7b8c9` (CP13 head).
  - Quote count: 26 records preserved.
  - Table `quote_revisions`: Does not exist.
  - Zero migrations or writes were run against the development database.
- **Test Database (`benchmark_test_db`):**
  - Schema created and seeded dynamically in transaction-isolated fixtures.
  - Fully verified for all CP14, CP15, and CP16 test executions.

---

## 7. Known Limitations

1. **Comparison / Diff Endpoint:** Comparing two revision snapshots (or diffing a historical revision against the live quote) is not part of CP16 and remains for CP17.
2. **Restoration Endpoint:** Restoring a past revision by creating a new revision snapshot is deliberately out of scope for CP16.
3. **Frontend UI History View:** CP16 strictly implements backend read-only retrieval endpoints; the UI history and revision inspector screens will be connected in subsequent phases.

---

## 8. Uncommitted Changes & Git Status

- `git status --short --branch`:
```text
## main...origin/main
 M backend/app/api/routers/quotes.py
 M backend/app/services/revision_service.py
?? backend/tests/test_quote_revision_retrieval.py
?? docs/CP16_HISTORICAL_REVISION_RETRIEVAL_CHECKPOINT.md
?? current-status.txt
?? current-untracked.txt
?? docs/CP12_SMTP_INVITATION_CHECKPOINT.md
?? docs/END_TO_END_TEST_PLAN.md
?? docs/PROJECT_CHECKPOINT_2026-10-12.md
?? docs/TEST_EXECUTION_REPORT.md
?? scratch/
```

- **Confirmation:** No commits, pushes, branch changes, or staging operations were performed. All pre-existing untracked files remain intact.

