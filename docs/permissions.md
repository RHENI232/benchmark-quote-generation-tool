# Roles & Access Control

Four business-facing tiers. Each tier is a strict superset of the one
before it — always check "is this user's tier ≥ X" rather than an exact
match.

| Tier | Can do |
|---|---|
| **Sales** | Build and save quotes. See/download Customer Copy export only. No Cost Price/Margin visibility anywhere. No catalog editing. |
| **Catalog Entry** | Everything Sales can, plus: edit catalog Sell/Cost Price, import catalog updates, set the Default Margin setting. Still no Cost Price/Margin visibility on quote preview or saved quotes, and no Internal/Tracking Sheet downloads. |
| **Management** | Everything Catalog Entry can, plus: Cost Price/Margin visibility on quote preview and saved quotes, Internal + Tracking Sheet downloads, Region/Legal Entity/Currency/Tax configuration. |
| **Admin** | Everything Management can, plus: define new Solutions (requirement schema + business rules), full user/role administration. |

## Enforcement rules
- Internal and Tracking Sheet downloads: restricted **server-side**
  (return 403 to anyone below Management), not just hidden client-side.
  Client-side hiding is a UX nicety only, never the actual guard.
- Never let a Sales-tier request return cost or margin fields, even if
  the frontend doesn't render them — check this at the API layer.
- Refuse any action (disable, delete, re-tier) that would leave **zero
  enabled Admin-tier accounts** — return a clear error rather than
  locking everyone out.

## Saved Quote visibility (Quote List & Search)
- Sales-tier users see **only quotes they own**.
- Catalog Entry, Management, and Admin see **every saved quote**, regardless of owner.
- List shows: row number, Client Name, Region/Country, Quote Generated Date.
- Search box matches Client Name.

## User Accounts — Phase 1 (this build)
- Admin (or a delegated User Admin) adds a user by email + assigns one
  of the four tiers.
- System sends a secure, time-limited **email invite link**; the user
  sets their own password on first login. No admin ever sees or sets a
  user's password.
- Passwords hashed with bcrypt or argon2. Never plaintext, never emailed.
- Self-service "forgot password" sends a fresh time-limited reset link.
- Admin can disable, re-enable, permanently delete an account, or change its tier.

## Phase 2 (not this build — documented for later)
Microsoft 365 / Entra ID SSO + directory sync. Manual and Entra-synced
accounts coexist; matching email addresses link into one user record
(no duplicates, quote history preserved). A manual account stays usable
for anyone outside the Microsoft tenant (e.g. external contractors).

## Not Included in v1
- Live/automatic FX rate updates — Region admin enters exchange rates manually.
- Schematic/block diagram export — descoped from this build.
