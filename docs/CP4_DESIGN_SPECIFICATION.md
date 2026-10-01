# FINAL CP-4 DESIGN SPECIFICATION
**Module:** Requirement Engine + Pricing Engine
**Baseline:** CP-3 commit `b906519`, Alembic revision `77cd83799512`

---

## 1. CP-4 scope and objectives
The objective of CP-4 is to introduce the core computational logic of the Presales Quote Tool: transforming captured client requirements into a finalized, priced, and snapshotted Quote. 
Scope includes: Requirement Engine (validation), Business Rules Engine (BOQ generation), Pricing Engine (margins, support calculation), FX/Tax application, and the Quote lifecycle API (preview, save, duplicate, recalculate).

## 2. Requirement Engine architecture
**Why it is needed:** To validate free-form JSON against defined Solution rules before passing it to business logic.
**What existing requirement it satisfies:** FR-2, FR-20, FR-21.
**CP-3 interaction:** Associates the requirement strictly with `Solution.requirement_schema`.
**Future behavior enabled:** Allows UI forms to be built dynamically based on the schema validation layer.

## 3. Requirement data model
The engine accepts raw JSON and maps it to a structured `RequirementPayload` dataclass.
Fields include `number_of_studios`, `news_production`, `sdi_production_ingest`, and nested `StudioRequirement` objects.
Dependency cascading (e.g., `production_playout = true` forces `mam = true`) happens here.

## 4. Business-rule model
**Why it is needed:** To map validated requirements to quantities of specific catalog items.
**What existing requirement it satisfies:** FR-22, Sections 4.1–4.8.
**CP-3 interaction:** Emits abstract BOM lines containing `lookup_key`, leaving catalog querying to a separate module.
**Future behavior enabled:** Allows rules to be versioned or swapped out independently of pricing.

## 5. Rule evaluation flow
1. **Receive:** Validated `RequirementPayload`.
2. **Evaluate Sections:** (Ingest, MAM, Playout, Graphics, etc.).
3. **Emit:** Raw BOM lines (`lookup_key`, `quantity`, `section`).
4. **Aggregate:** Sum quantities of identical `lookup_key`s within the same section.
5. **Output:** List of `BOMLineSpec`.

## 6. Catalog lookup strategy using lookup_key
**Why it is needed:** To safely retrieve catalog pricing without relying on mutable/non-unique part numbers.
**What existing requirement it satisfies:** CP-3 core architectural invariant; FR-23.
**CP-3 interaction:** The Pricing Engine will query `CatalogItem` by `lookup_key`. The `cat_wtv_` and `cat_usr_` identities are strictly respected.
**Future behavior enabled:** Catalog items can be renamed, have their part numbers updated, or undergo price changes, while the rule engine continues referencing the immutable `lookup_key`.

## 7. Pricing Engine architecture
The Pricing Engine takes the resolved Catalog Items and computes the financials. It is strictly separated from the Requirement Engine.
**Flow:** Apply quantities → Calculate unit prices → Calculate Support (last) → Apply Margin → Produce Subtotals (USD).

## 8. Quantity calculation
Quantities are strictly positive integers calculated by the Business Rules Module (using ceiling division where required, e.g., `math.ceil(channels / 4)`).

## 9. Cost-price calculation
Unit Cost Price is fetched from `CatalogItem.cost_price`.
If `cost_price` is NULL, it is treated as `$0.00` (with a `price_placeholder` flag) to allow quote generation without blocking on data gaps.

## 10. Sell-price calculation
Unit Sell Price is fetched from `CatalogItem.sell_price`.
If `sell_price` is NULL, it is treated as `$0.00` (with a `price_placeholder` flag).
Line Sell Total = `quantity × unit_sell_price`.

## 11. Margin calculation and zero-value guards
**Why it is needed:** To ensure mathematically sound profit metrics and prevent application crashes.
**What existing requirement it satisfies:** FR-30 (guarded against division by zero).
**Formula:** `((Sell - Cost) / Sell) * 100`
**Guard:** If `Sell == 0`, Margin % is strictly `0.00%`. Negative margins (Cost > Sell) are permitted.

## 12. FX conversion rules
**Why it is needed:** To support international quotes while keeping the base catalog in USD.
**What existing requirement it satisfies:** FR-25, FR-25.1.
**Flow:** Applies `Region.fx_rate_to_usd` (local units per 1 USD) to the USD subtotals to produce local currency totals. USD quotes inherently use a 1.0 rate.

## 13. Tax calculation
**Why it is needed:** To apply regional taxes cleanly at the end of the quote.
**What existing requirement it satisfies:** FR-27.
**Flow:** Calculated *after* FX conversion. Tax is applied to the local currency subtotal using `Region.tax_rate_percent`.

## 14. Quote and QuoteLineItem snapshot strategy
**Why it is needed:** To guarantee that past quotes do not silently change when underlying catalog/region data changes.
**What existing requirement it satisfies:** Implicit requirement for professional quoting; auditability.
**Implementation:** `Quote` will snapshot FX rate, tax rate, legal entity. `QuoteLineItem` will snapshot sell price, cost price, description, part number, margin, and section.

## 15. Quote recalculation/versioning behavior
**Why it is needed:** To allow drafts to absorb recent catalog updates.
**Implementation:** Recalculation is explicit:
- `Quote.version` is a recalculation/version counter.
- Recalculating a DRAFT quote re-runs the full pipeline, overwrites the active DRAFT snapshot, and increments the counter (preserving the Quote ID/URL).
- Previous DRAFT calculation states are NOT retained as historical versions in the database.
- Historical immutability begins when the quote status becomes SAVED.
- SAVED quotes retain their exact snapshot and cannot be recalculated or modified.

## 16. Quote immutability/history rules
**Why it is needed:** To lock pricing when a quote is sent to a client.
**Implementation:** Quotes in `SAVED` status are strictly immutable. They cannot be recalculated or modified. To revise a SAVED quote, the user must use the `Duplicate` action to create a new DRAFT.

## 17. Permission/RBAC behavior
**Why it is needed:** To enforce corporate governance.
**What existing requirement it satisfies:** Permissions Matrix (§5).
**Behavior:**
- `Sales`, `Catalog Entry`, `Management`, `Admin` can create/preview/duplicate quotes.
- `Sales` can only view/list their own quotes.
- `cost_visibility` permission is required to see cost/margin data in the API response.

## 18. Error and validation behavior
- HTTP 422: Validation errors (e.g., negative quantities, missing FX rate).
- HTTP 409: Business conflicts (e.g., recalculating a SAVED quote, catalog item `lookup_key` missing from DB).
- HTTP 403: Authorization errors.

## 19. API boundaries
| Endpoint | Action | State Target |
|---|---|---|
| `POST /api/quotes/preview` | Stateless engine execution | None |
| `POST /api/quotes` | Create quote | DRAFT |
| `GET /api/quotes` | List quotes (scoped by role) | DRAFT/SAVED |
| `GET /api/quotes/{id}` | Retrieve quote | DRAFT/SAVED |
| `PUT /api/quotes/{id}` | Edit headers (no pricing impact) | DRAFT |
| `POST /api/quotes/{id}/recalculate` | Update pricing | DRAFT |
| `POST /api/quotes/{id}/save` | Lock quote | DRAFT -> SAVED |
| `POST /api/quotes/{id}/duplicate` | Copy requirement to new quote | SAVED/DRAFT -> New DRAFT |

## 20. Database changes required for CP-4
No code is written yet, but the design dictates adding snapshot columns.
- **Quote:** `currency_code`, `fx_rate_to_usd`, `fx_rate_as_of`, `tax_enabled`, `tax_rate_percent`, `subtotal_sell_usd`, `subtotal_cost_usd`, `tax_amount`, `total_sell_local`, `legal_entity_*`.
- **QuoteLineItem:** `line_sell_total`, `line_cost_total`, `margin_percent`.

## 21. Migration strategy
**Why it is needed:** To instantiate the snapshot columns safely.
**Implementation:** A standard Alembic migration adding the columns described in §20. Defaults will be applied, though no production quote data exists yet to migrate.

## 22. Test strategy
- **Unit Tests:** Requirement parsing, individual WTVision rules, pricing formulas (zero-guard, negative margins), FX calculations.
- **Integration Tests:** Full quote lifecycle API (Preview -> Draft -> Recalculate -> Save -> Duplicate).
- **Security Tests:** Cost visibility masking, quote owner scoping.

## 23. CP-3 regression requirements
All 46 existing tests for CP-3 must pass. The CP-3 `CatalogItem.lookup_key` invariants (immutability, reset survival, UUID generation) must remain entirely untouched. `QuoteLineItem` relationships must not interfere with `CatalogItem` soft/hard-delete blocks.

## 24. Explicit resolution of OD-1
**OD-1 (Pricing Lifecycle):** Resolve the contradiction between FR-23 (live catalog updates) and Quote Immutability.
**Resolution:** Hybrid model.
1. **What is stored:** Complete snapshots of prices, margins, FX, tax, and descriptions on the Quote and QuoteLineItem upon creation.
2. **Recalculable?:** Yes, for `DRAFT` quotes only, via explicit user action (`/recalculate`). `SAVED` quotes are locked forever.
3. **Historical Snapshots:** Intact. Recalculation applies to the active draft. Saved quotes retain their precise historical state, surviving catalog resets.
4. **When catalog changes:** It does NOT automatically cascade to quotes. The user must click recalculate on their draft.
5. **Versioning:** Recalculating mutates the existing draft row but increments the `Quote.version` column.

## 25. Explicit resolution of OD-2
**OD-2 (Missing FX rate):** Define exact behavior when a non-USD region has no FX rate.
**Resolution:** Explicit Blocking.
- If `Region.currency_code == 'USD'`, the FX rate is mathematically `1.0`.
- If `Region.currency_code != 'USD'` and `Region.fx_rate_to_usd` is NULL, zero, or negative, the quote engine **REJECTS** the calculation (HTTP 422).
- It will NOT silently fallback to 1.0. The API will return an error instructing the user to configure the FX rate.

## 26. Explicit resolution of OD-3
**OD-3 (Requirement/Business Rule architecture):** Configurable rules vs Hardcoded logic.
**Resolution:** Phased Hybrid Architecture.
- **Requirement data:** Arbitrary JSON stored on the Quote, strictly validated by the Python engine against a schema.
- **Rule definitions & Evaluation:** In CP-4, these are **hardcoded in Python** (`wtvision_graphics.py`).
- **Catalog references:** Hardcoded `lookup_key` strings (e.g., `cat_wtv_000001`) in the Python logic.
- **Pricing:** A generic decoupled Pricing Engine.
- **Deferred:** Building an AST/JSON-based dynamic evaluator in the database is intentionally deferred to avoid over-engineering CP-4. Python modules mapping `solution_id` to logic satisfy the current single-solution scope efficiently.

## 27. Deferred/out-of-scope functionality
- Excel Export generation (CP-5).
- Frontend implementations.
- Database-driven UI for Rule Configuration.
- AI Requirement Parsing.

## 28. Risks and tradeoffs
- **Risk:** `brand` is NULL for all 44 seed items. Support calculation will correctly compute $0 until data is populated.
- **Risk:** Python-based rule engine deviates from strict reading of FR-4 (UI rule configuration), traded off for delivery speed and testability.
- **Risk:** Placeholder null prices in the catalog might confuse users if generated in a quote before the price is negotiated.

## 29. CP-4 implementation sequence
1. Implement Alembic migration for Quote/LineItem snapshots.
2. Build Requirement Engine validation layer.
3. Build Business Rules Dispatcher and `wtvision_graphics.py`.
4. Build Pricing, FX, and Tax Engine logic.
5. Assemble the `quote_service.py` lifecycle orchestrator.
6. Build API routers and schemas.
7. Write and pass all test layers.

## 30. Acceptance criteria
- [ ] DRAFT quotes snapshot prices and can be recalculated to absorb catalog changes.
- [ ] SAVED quotes cannot be recalculated or modified.
- [ ] `lookup_key` is the sole anchor for catalog resolution in the rules engine.
- [ ] Non-USD quotes without an FX rate explicitly throw HTTP 422.
- [ ] Margin division by zero is safely guarded to 0.00%.
- [ ] 100% of CP-3 tests continue to pass.

---

### HUMAN APPROVAL CHECKPOINT

- **Decisions requiring approval:** Resolution of OD-1 (Hybrid), OD-2 (Explicit block), and OD-3 (Hardcoded Python dispatcher).
- **Conflicts found:** Contradiction between FR-23 live updates vs professional quote immutability (resolved via Hybrid model).
- **Deviations:** Deferring database-configurable rules to a future phase in favor of testable Python.
- **Database schema changes required:** Adding snapshot columns (`fx_rate_to_usd`, `subtotal_sell_usd`, etc.) to the quotes tables. No changes to catalog tables.
- **Risks that could affect CP-3:** None. The catalog structure remains fully read-only from the perspective of the quote engine.
- **Exact statement:** "NO CP-4 CODE SHOULD BE IMPLEMENTED UNTIL THIS SPECIFICATION IS APPROVED."
