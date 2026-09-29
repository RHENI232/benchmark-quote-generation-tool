# Where the real specification lives
Do not invent, guess, or approximate any business rule. Everything needed
already exists in docs/:

- docs/requirements.md — the full original specification (functional
  requirements FR-1 through FR-54, non-functional requirements, roles,
  risks, glossary). This is the authoritative source. Read it before
  writing code for any feature.
- docs/pricing-rules.md — the exact calculation engine formulas (Section 4
  of requirements.md), with part numbers, quantities, and worked examples.
  Treat every formula here as validated and tested — do not "simplify" or
  "improve" a formula without asking first.
- docs/data-model.md — the entities/tables needed and the full requirement
  form field list with show/hide dependencies.
- docs/permissions.md — the four-tier role matrix and enforcement rules.

# Non-negotiable business rules (worth repeating because they're easy to get wrong)
- Section 4.9 (3 Years Standard Support) must be calculated LAST — it
  depends on the totals of every other section.
- The Part Number "BDLKDVQD2" refers to TWO different catalog items
  (Ingest Capture Card vs Graphics IO card) with different prices. Do not
  merge them into one catalog row.
- Quote exports are THREE SEPARATE FILES (Customer Copy, Internal,
  Tracking Sheet) — never one workbook with multiple tabs. See
  docs/data-model.md, "Export Files".
- Cost Price is never auto-recalculated when Sell Price or the Default
  Margin setting changes later — it's independently editable once set.
- Sections/studios with zero line items are omitted from both the live
  preview and the export — not shown as empty.
