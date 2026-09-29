# Project Identity
Display name (shown in the app UI, page title, quote letterhead references,
README title): "Benchmark Quote Generation Tool"
Folder / repo / package name (kebab-case, used everywhere else — folders,
package.json, Docker container names, git repo): benchmark-quote-generation-tool
Python package/module name (snake_case): benchmark_quote_generation_tool

# Tech Stack — do not change without asking
- Frontend: JavaScript (React)
- Backend: Python (FastAPI)
- Database: PostgreSQL
No other languages or frameworks without explicit confirmation.

# Explicitly OUT of scope for this build
- No SSO / Microsoft Entra ID login (Phase 2 — documented in
  docs/permissions.md but not to be built now)
- No SVG / block diagram export (descoped entirely, not deferred)
- No live/automatic FX-rate API — exchange rates for non-USD regions are
  entered and updated manually by a Management/Admin user
  (see docs/data-model.md, Region entity)

# Explicitly IN scope (don't skip these)
- Automated email invite for new manual user accounts (see
  docs/permissions.md, "User Accounts — Phase 1") — this DOES require a
  real email-sending service/provider (e.g. SendGrid, AWS SES, or SMTP).
  Ask which provider to use before implementing; don't assume one.
- Free-text/AI requirement capture (calls an external AI/LLM API) — see
  docs/requirements.md Section 3.4. Human review is mandatory before any
  AI-extracted data reaches a priced quote.
