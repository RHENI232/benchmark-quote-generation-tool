# Data Model — Quote Generation Tool

Source: WTVision_Requirements_v3.4, Sections 3.1–3.10. This describes
the tables/entities needed; exact column types are the agent's job to
propose, but every field listed here must exist somewhere.

## Solution
One row per product line (e.g. "WTVision Graphics", "OTT Platform").
- id, name
- requirement_schema (defines the form fields/sections for this Solution)
- business_rules (the formula set — see pricing-rules.md for the WTVision
  Graphics example)
- default_margin_percent (overridable per Solution, default 15%)

Everything downstream (Requirement form, Catalog, live preview, export)
is driven by the selected Solution's configuration — never hardcode a
specific Solution's logic into shared code.

## Catalog Item
Per Solution. Two kinds:
- **Rule-Driven Part** — Part Number is fixed/not editable (the calc
  engine looks it up by exact code). Description, Brand, Sell Price,
  Cost Price ARE editable.
- **Reference Part** — everything editable including Part Number, can be
  freely added/removed. Pricing-reference only, never auto-added to a quote.

Fields: part_number, description, brand, sell_price, cost_price, solution_id, kind (rule_driven | reference)

Note: the same displayed Part Number text can map to two different
internal rows (e.g. BDLKDVQD2 — see pricing-rules.md). Do not assume Part
Number is globally unique; it's unique per (solution_id, kind, internal row).

## Region
- id, country_name
- currency_code
- legal_entity_name, legal_entity_registration_number, legal_entity_address, legal_entity_contact
- tax_enabled (bool), tax_rate_percent
- fx_rate_to_usd, fx_rate_as_of (manually entered for now — see Open Items)

Launch data: Singapore (USD, Benchmark Broadcast Systems (S) Pte Ltd, no
tax) and India (INR, entity TBC, India GST — rate TBC with Finance).

## Quote
- id, solution_id, region_id
- client_name, quote_ref_no, date, attention, description, version
- requirement_data (the full filled-in requirement form, per-studio included)
- created_by_user_id, last_edited_by_user_id, created_at, updated_at
- status (draft/saved)

## Quote Line Item (computed, not stored as authored input)
- quote_id, catalog_item_id (reference, so a later catalog price change
  reflects on recompute), quantity, unit_sell_price_snapshot, unit_cost_price_snapshot

Recomputed on every Requirement field change (target: under 1 second for
up to 12 studios). Sections with zero line items are omitted from both
the live preview and the export.

## User
- id, email, role_tier (Sales | Catalog Entry | Management | Admin)
- account_type (manual | entra_synced)
- password_hash (manual accounts only — never plaintext)
- enabled (bool)
- entra_object_id (Phase 2, nullable)

Manual and Entra-synced accounts link by matching email into a single
user record (no duplicates). System must refuse any action that would
leave zero enabled Admin-tier accounts.

## Requirement Schema (example: WTVision Graphics Solution)

### Main Requirement (quote-level)
| Field | Type | Depends on |
|---|---|---|
| Number of Studios | 1–12 | — |
| Number of Designers | 0+ | — |
| News Production | Yes/No | auto-forced on by MOS Redundancy or NRCS Graphics Preview |
| Journalists | 10 / 25 / 50 | shown only if News Production |
| MOS Redundancy | Yes/No | forces News Production on |
| Avid/Adobe NLE Plugin | Yes/No | — |
| NLE Seats | 5 / 10 / 15 | shown only if NLE Plugin |
| NRCS Graphics Preview | Yes/No | forces News Production on |
| SDI Production Ingest | Yes/No | — |
| Ingest Channels | 0+ | meaningful only if SDI Production Ingest |
| Production Playout | Yes/No | forces MAM on |
| MAM | Yes/No | locked ON while Production Playout selected |
| 3 Years Standard Support | Yes/No | pricing in Section 4.9 of pricing-rules.md |

### Per-Studio (repeated 1–12 times)
| Field | Type | Depends on |
|---|---|---|
| Studio Type | Real Set / VR-AR (R3 Engine) / VR-AR (Unreal) | — |
| Number of Cameras | 1 / 2 / 3 | shown only if Studio Type = VR-AR (Unreal) |
| LED Video Wall | Yes/No | — |
| LED Outputs | 4 / 8 | shown only if LED Video Wall |
| Number of Engines | 0+ | — |
| Dual Channel | Yes/No | shown only if Engines ≥ 1 |
| Extra Live Input | Yes/No | shown only if Engines ≥ 1 |
| Number of Control Clients | 0+ | aggregated across all studios for Playout Controller |

Dependent fields must show/hide in real time as the form is edited — no page reload.

## Export Files (per quote, three separate downloads — never one workbook with tabs)
1. **Customer Copy** — sell price only, Region's letterhead/currency, anyone can download.
2. **Internal** — + Cost Price, Total Cost, Margin %, always USD, Management/Admin only.
3. **Tracking Sheet** — cost/sell rollup by product section and brand, Management/Admin only.

All three preserve Excel formulas (not static numbers). Blank-row gap between sections.
Margin % = (Sell − Cost) ÷ Sell × 100, guarded against divide-by-zero.

## Requirement Import/Export (separate feature from the priced quote export)
Exports/imports the Requirement form itself (inputs, not prices) as a
spreadsheet — for offline requirement gathering. Every field with a fixed
value set gets a dropdown (strict validation = reject out-of-list;
open-ended counts = suggested-values dropdown that warns but allows
override). Parsed by field label, not fixed cell position.
