# Project Checkpoint: CP12 — SMTP Invitation, User Activation & Authentication Stabilization

- **Date:** 2026-10-14
- **Project:** Benchmark Broadcast Systems — Presales Quote Tool
- **Repository:** `benchmark-quote-generation-tool`
- **Checkpoint:** `CP12`
- **Phase:** SMTP Invitation, User Activation and Authentication Stabilization
- **Branch:** `main`
- **Baseline Commit:** `6791add46c8e8cb92fb916a530ac7e7ce9771125` (`CP11 complete customer PDF quotation export checkpoint`)

---

## 1. Project Identity and Checkpoint Identifier

- **Application Name:** Benchmark Broadcast Systems — Presales Quote Tool
- **Display Name:** Benchmark Quote Generation Tool
- **Package / Module:** `backend.app`
- **Checkpoint Identifier:** `CP12`
- **Scope:** Delivery of a secure, configurable user invitation workflow (supporting local console logging and Gmail SMTP via STARTTLS with Google App Passwords), resolution of invitation acceptance and user status lifecycle ("Pending Invite" vs "Active" vs "Disabled"), and stabilization of CORS preflight and frontend authentication communication.

---

## 2. Summary of Completed Functionality

### A. Configurable Email Invitation Delivery System
- **Provider Switching:** Added support for `EMAIL_PROVIDER=console` (development/testing) and `EMAIL_PROVIDER=gmail` (production/staging) controlled via environment configuration without code changes.
- **Gmail SMTP Engine:** Standard library `smtplib` implementation utilizing explicit STARTTLS encryption on port 587 with Google App Password authentication.
- **6-Stage Connection Lifecycle:**
  1. TCP connection with a 15-second timeout.
  2. Initial EHLO greeting.
  3. STARTTLS cryptographic negotiation (`ssl.create_default_context()`).
  4. Post-TLS EHLO re-greeting.
  5. Authentication (`AUTH PLAIN` / `AUTH LOGIN`) with specialized error detection for Gmail's `535 BadCredentials` anti-brute-force socket disconnection.
  6. Multipart message submission (clean plain-text alternative and responsive HTML template).
- **Security & Secret Sanitization:**
  - Raw cryptographic tokens (`secrets.token_urlsafe(32)`) and acceptance URLs are omitted from API responses when `EMAIL_PROVIDER=gmail` or `ENVIRONMENT != development`.
  - Passwords and raw invitation tokens are strictly excluded from all application logs and error messages.
  - User-facing error responses return clean, sanitized HTTP status codes (`502 Bad Gateway` on delivery failure) without leaking internal tracebacks or server details.
- **Transactional Atomicity & Rollback:**
  - `POST /api/users/invite` creates staged database records (`User`, `InviteToken`) using `db.flush()`.
  - If SMTP transmission fails (`EmailDeliveryError`, `EmailConfigError`, socket drop), `db.rollback()` is executed immediately, leaving zero phantom users or orphaned tokens in PostgreSQL.

### B. Invitation Lifecycle, Resend & Acceptance Flow
- **Token Security:** 256 bits of cryptographic entropy, stored exclusively as SHA-256 hashes (`token_hash`) with a strictly enforced 72-hour expiration window (`expires_at`).
- **Resend Invalidation:** `POST /api/users/{user_id}/resend-invite` invalidates all existing unused tokens (`used_at = now_utc`) before issuing a fresh 72-hour token.
- **Single-Use Enforcement:** `POST /api/auth/invite/accept` marks `used_at = now_utc`, hashes the new password with bcrypt, and transitions `user.enabled = True`.

### C. User Status & Administration Panel Stabilization
- **Status Lifecycle Representation:**
  - **Pending Invite:** Unactivated manual user (`password_hash is None and not enabled and account_type == MANUAL`). Rendered as amber badge (`Pending Invite`) with a **Resend Invite** action button.
  - **Active:** Activated, enabled user (`enabled is True`). Rendered as green badge (`Active`) with a **Disable** action button.
  - **Disabled:** Manually disabled user (`enabled is False and password_hash is not None`). Rendered as neutral badge (`Disabled`) with an **Enable** action button.
- **Computed Status Property:** Added `@property def status` on `User` model and `status: Optional[str] = None` on `UserResponse` schema for consistent API serialization.
- **UI Refresh & Stale Data Prevention:**
  - Added dedicated **Refresh** action button in `PageHeader` on `UserAdminPage.jsx`.
  - Added a `window` `focus` event listener in `UserAdminPage.jsx` to automatically refresh user listings when an administrator returns to the tab after an invitation is accepted.
  - Added HTTP `Cache-Control: no-cache, no-store, must-revalidate` response headers on `GET /api/users` and scoped frontend `Cache-Control` headers to non-mutation GET requests in `client.js`.

### D. CORS Preflight & Authentication Stabilization
- **Allowed Origins:** Explicit whitelist containing:
  - `http://localhost:5173`
  - `http://127.0.0.1:5173`
  - `http://192.168.229.41:5173` (preserved local LAN origin)
- **Preflight Header Compatibility:** Configured `allow_headers=["*"]` in FastAPI `CORSMiddleware`, allowing browser preflight `OPTIONS` requests requesting `Content-Type`, `Authorization`, `Cache-Control`, `Pragma`, and `Accept` to succeed with `200 OK`.
- **Preflight Methods:** Allowed methods `["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]` with `allow_credentials=True`.

---

## 3. Architecture and Affected Components

```
[Browser / React Client]
  │
  ├──► OPTIONS /api/auth/login ──► FastAPI CORSMiddleware (Returns 200 OK + Allow-Origin)
  ├──► POST /api/auth/login ─────► auth.py (JWT Authentication)
  │
  ├──► GET /api/users ───────────► users.py (Cache-Control: no-cache, returns List[UserResponse])
  │                                   │
  │                                   ▼
  │                                 User.status ("Pending Invite" | "Active" | "Disabled")
  │
  ├──► POST /api/users/invite ───► users.py (Staged db.flush())
  │                                   │
  │                                   ├──► email_service.py (STARTTLS / smtp.gmail.com:587)
  │                                   │      ├── On Success: db.commit() -> 201 Created
  │                                   │      └── On Failure: db.rollback() -> 502 Bad Gateway
  │
  └──► POST /api/auth/invite/accept ──► auth.py (Validates hash, sets password, enabled=True, used_at=now)
```

### Component Details
- `backend/app/services/email_service.py`: Standalone delivery module with console logging, Gmail SMTP client, HTML email templating, and custom exception hierarchy (`EmailConfigError`, `EmailConnectionError`, `EmailAuthError`, `EmailDeliveryError`).
- `backend/app/api/routers/users.py`: Protected admin endpoints for user listing, invitation creation, resend, status updates, and deletions.
- `backend/app/api/routers/auth.py`: Public authentication, password reset, and invitation acceptance endpoints.
- `backend/app/models/user.py`: SQLAlchemy `User` model with computed `is_pending_invite` and `status` properties.
- `backend/app/schemas/user.py`: Pydantic `UserResponse` with `is_pending_invite` and `status` fields.
- `backend/app/core/config.py`: Pydantic settings loading SMTP parameters from `.env`.
- `backend/app/main.py`: Application entrypoint, router aggregation, and `CORSMiddleware`.
- `frontend/src/pages/UserAdminPage.jsx`: Administration UI with dynamic badges, resend/disable actions, manual refresh, and focus auto-fetch.
- `frontend/src/api/client.js`: HTTP fetch wrapper with authorization header injection and GET cache-control headers.

---

## 4. Environment Configuration Reference

The following configuration variables are supported in `.env` (illustrated with safe placeholders; **no actual credentials**):

```ini
# Application Environment
ENVIRONMENT=development

# Database Configuration
DATABASE_URL=postgresql+psycopg://postgres:<PASSWORD>@localhost:5432/benchmark_quote_generation_tool

# Security & JWT
JWT_SECRET_KEY=<SECURE_RANDOM_SECRET_KEY>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Frontend Host URL (for constructing invitation links)
FRONTEND_URL=http://localhost:5173

# Email Delivery Configuration
# Options: "console" (development default) or "gmail" (SMTP delivery)
EMAIL_PROVIDER=console

# Gmail SMTP Parameters (required only when EMAIL_PROVIDER=gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=user@example.com
SMTP_PASSWORD=abcd efgh ijkl mnop
SMTP_FROM_EMAIL=user@example.com
SMTP_FROM_NAME=Benchmark Broadcast Systems
```

> [!IMPORTANT]
> When `EMAIL_PROVIDER=gmail`, Google requires a dedicated **16-character Google App Password** generated under Google Account Security (with 2-Step Verification active). Standard account passwords are intentionally rejected by Gmail SMTP.

---

## 5. Verification Results

### A. Current Full Backend Test Suite
Executed:
```powershell
$env:PYTHONPATH="."; backend\.venv\Scripts\pytest backend/tests/ -q
```
- **Result:** **150 passed**, 1672 deprecation warnings in 77.75s.
- **Coverage breakdown:**
  - `test_auth.py`: 9 passed (including CORS preflight allowed origins and disallowed origin rejection).
  - `test_email_service.py`: 11 passed (headers, HTML escaping, console delivery, Gmail success, missing config, auth failure, connection failure, TLS negotiation failure, server disconnect error classification, message data delivery error, invalid provider).
  - `test_users.py`: 15 passed (listing, invite creation, 403 non-admin, admin invariants, quote history delete protections, Gmail token omission, delivery failure transaction rollback, resend token invalidation, active user resend prevention, full activation lifecycle & status transition).
  - `test_quotes.py`: 60 passed (Phase 11 customer PDF generation, urgency transitions, approval queue ordering, concurrency row locking, financial masking).
  - `test_catalog.py`: 12 passed.
  - `test_solutions.py`: 13 passed.
  - `test_pricing_engine.py`: 9 passed.
  - `test_requirement_engine.py`: 5 passed.
  - `test_seed.py`: 5 passed.
  - `test_models.py`: 4 passed.
  - `test_rbac.py`: 4 passed.
  - `test_regions.py`: 2 passed.

### B. Current Frontend Linting
Executed:
```powershell
npm run lint
```
- **Result:** **0 errors**, 18 pre-existing warnings across 28 files (exit code 0).

### C. Current Frontend Production Build
Executed:
```powershell
npm run build
```
- **Result:** **Built successfully in 493ms** (exit code 0).
  - `dist/index.html`: 0.47 kB
  - `dist/assets/index-HfZUjIih.css`: 17.40 kB
  - `dist/assets/index-CXsPxHGn.js`: 369.15 kB

---

## 6. Manual Verification Performed

1. **Gmail SMTP Delivery:**
   - Configured `.env` with live Google App Password credentials.
   - Dispatched invitation from `/users` to an external inbox.
   - Confirmed receipt of multipart email with Benchmark styling, expiration disclaimer (72 hours), and clickable activation button.
2. **Invitation Acceptance & Password Setup:**
   - Navigated to `/invite/accept?token=...`.
   - Set password and confirmed account activation (`200 OK`).
3. **User Administration Status Reflection:**
   - Returned to administrator browser tab at `/users`.
   - Verified that user transitioned from amber **Pending Invite** badge to green **Active** badge.
   - Verified action button toggled from **Resend Invite** to **Disable**.
4. **Login Verification:**
   - Signed in as the newly activated user at `/login`.
   - Confirmed JWT issuance and successful redirection to `/`.
   - Verified role-based navigation guards restricted access to authorized screens only.
5. **CORS Preflight Verification:**
   - Browser console confirmed `OPTIONS /api/auth/login` returned `200 OK` from `http://localhost:5173`.
   - No `net::ERR_FAILED` or preflight error warnings.

---

## 7. Files Changed in CP12

| File Path | Description of Change |
|---|---|
| `.env.example` | Added documentation and placeholders for SMTP settings and `FRONTEND_URL`. |
| `backend/app/api/routers/users.py` | Implemented `invite_user`, `resend_invite`, delivery failure rollback, and `Cache-Control` response headers on `list_users`. |
| `backend/app/core/config.py` | Added Pydantic Settings for `EMAIL_PROVIDER`, `SMTP_*`, and `FRONTEND_URL`. |
| `backend/app/main.py` | Configured CORS allowed origins (`localhost`, `127.0.0.1`, LAN origin) and set `allow_headers=["*"]`. |
| `backend/app/models/user.py` | Added `@property is_pending_invite` and `@property status` to `User` model. |
| `backend/app/schemas/user.py` | Added `is_pending_invite` and `status` fields to `UserResponse`. |
| `backend/app/services/email_service.py` | **New file:** Full email service implementation (console + Gmail SMTP). |
| `backend/tests/test_email_service.py` | **New file:** 11 mocked unit tests for email delivery and diagnostic classification. |
| `backend/tests/test_auth.py` | Added 2 CORS preflight test cases (`OPTIONS /api/auth/login`). |
| `backend/tests/test_users.py` | Added test isolation fixture and 6 CP12 integration tests. |
| `frontend/src/api/client.js` | Scoped cache-busting headers to non-mutation GET requests. |
| `frontend/src/api/userApi.js` | Added `resendInvite(userId)` client API function. |
| `frontend/src/pages/UserAdminPage.jsx` | Added Resend Invite button, updated status badge rendering, added Refresh button, and added focus auto-fetch. |

---

## 8. Existing Unrelated Changes Preserved

The following existing configurations and untracked files have been strictly preserved:
- **LAN CORS Origin:** `http://192.168.229.41:5173` in `backend/app/main.py`.
- **Existing Untracked Files:**
  - `current-status.txt`
  - `current-untracked.txt`
  - `docs/PROJECT_CHECKPOINT_2026-10-12.md`
  - `scratch/` directory and contents

---

## 9. Known Issues and Deferred Work

1. **Synchronous Email Delivery:**
   - Email dispatch currently occurs synchronously within the `POST /api/users/invite` request cycle (with a 15-second timeout and rollback). An asynchronous worker queue (Celery, ARQ, or BackgroundTasks) is deferred to production infrastructure hardening.
2. **Database Migrations:**
   - No database schema migrations were added. All necessary columns (`password_hash`, `enabled`, `account_type`, `InviteToken` table) already existed in the database.
3. **Microsoft 365 / Entra ID SSO (FR-47 through FR-49):**
   - Stored in backlog for future enterprise directory synchronization.
4. **Automated Live XE Currency Feed (FR-25, FR-26):**
   - Manual FX rate entry in Regional settings remains active and supported.

---

## 10. Exact Git Status

- **Branch:** `main`
- **Latest Upstream Commit:** `6791add` (`CP11 complete customer PDF quotation export checkpoint`)
- **Working Tree Summary (`git status --short`):**
  ```text
  M .env.example
  M backend/app/api/routers/users.py
  M backend/app/core/config.py
  M backend/app/main.py
  M backend/app/models/user.py
  M backend/app/schemas/user.py
  M backend/tests/test_auth.py
  M backend/tests/test_users.py
  M frontend/src/api/client.js
  M frontend/src/api/userApi.js
  M frontend/src/pages/UserAdminPage.jsx
  ?? backend/app/services/email_service.py
  ?? backend/tests/test_email_service.py
  ?? current-status.txt
  ?? current-untracked.txt
  ?? docs/CP12_SMTP_INVITATION_CHECKPOINT.md
  ?? docs/PROJECT_CHECKPOINT_2026-10-12.md
  ?? docs/PROJECT_CHECKPOINT_CP12_2026-10-14.md
  ?? scratch/
  ```

---

## 11. Instructions to Restart Services

### Backend Service (FastAPI / Uvicorn)
1. Stop the current Uvicorn process using `Ctrl + C`.
2. Start the server from the repository root:
   ```powershell
   backend\.venv\Scripts\uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Frontend Service (Vite / React)
1. Stop the current Vite process using `Ctrl + C`.
2. Start the development server from the `frontend` directory:
   ```powershell
   cd frontend
   npm run dev -- --host 0.0.0.0 --port 5173
   ```

---

## 12. Next-Phase Recommendation

Based on the project roadmap and phase plan:

- **Recommended Phase:** **CP13 — Offline Requirement Spreadsheet Import & Export (FR-37 through FR-41)**
  - **Objective:** Enable presales engineers to download an offline Excel workbook template reflecting the requirement schema for a solution, fill it out offline at customer sites, and import the completed spreadsheet back into the guided wizard to auto-populate the Bill of Materials.
  - **Alternative Option:** Production deployment readiness (Docker containerization, Celery background worker queue for email dispatch, and production environment hardening).
