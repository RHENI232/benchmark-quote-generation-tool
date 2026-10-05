# CP7 DESIGN SPECIFICATION: Frontend Foundation & Core Quote UI

## 1. Purpose
The purpose of the CP7 (Checkpoint 7) phase is to establish the first usable frontend application for the `benchmark-quote-generation-tool`. It provides a graphical interface for the functionally complete FastAPI backend, enabling users to log in securely, navigate an application shell, and view/search their saved quotes.

## 2. Scope
CP7 strictly implements the frontend foundation and the read-only core quoting interface.
In scope:
- React frontend foundation and JavaScript project structure.
- Login page and JWT authentication integration.
- Logout functionality and protected application routes.
- Standard application layout (header, navigation).
- A basic Dashboard.
- A paginated, searchable Quote List.
- Loading states, empty states, and API error states.
- Role-aware UI behavior (UX visibility).

## 3. Technology Stack
Per strict project requirements, the technology stack is:
- **Core Library:** React
- **Language:** JavaScript (ES6+)
- **Styling:** Standard CSS
- **Routing:** React Router (e.g., `react-router-dom`)
- **HTTP Client:** Native `fetch` API

*Explicitly banned technologies:* TypeScript, Next.js, Tailwind CSS, shadcn/ui, Material UI, and heavy state-management libraries (e.g., Redux).

## 4. Frontend Architecture
The frontend will be built as a standard Single Page Application (SPA).
- **State Management:** Core state (e.g., the authenticated user profile and JWT) will be managed using standard React Context (`AuthContext`). Local component state (e.g., search inputs, pagination) will use `useState`/`useReducer`.
- **Component Design:** Components will be functionally separated into layouts, page views, and reusable UI primitives (buttons, inputs, tables).
- **API Integration:** A centralized wrapper around the native `fetch` API will intercept requests to inject the JWT and intercept responses to handle global errors (e.g., 401 Unauthorized).

## 5. Folder Structure
The application will reside in the `/frontend` directory with the following structure:
```text
frontend/
├── public/              # Static assets (index.html, favicon)
├── src/
│   ├── api/             # Centralized fetch wrapper and endpoint functions
│   ├── components/      # Reusable UI components (Button, Input, Table)
│   ├── contexts/        # React Context providers (AuthContext)
│   ├── layouts/         # Page shells (AppLayout, AuthLayout)
│   ├── pages/           # Route-level components (Login, Dashboard, QuoteList)
│   ├── styles/          # Standard CSS files
│   ├── utils/           # Helper functions (date formatting, currency)
│   ├── App.jsx          # Root component and route definitions
│   └── index.js         # React DOM entry point
└── package.json
```

## 6. Routing
React Router will define the following hierarchy:
- **Public Routes:**
  - `/login`: The authentication screen.
- **Protected Routes** (wrapped in a route guard):
  - `/`: The Dashboard (authenticated landing page).
  - `/quotes`: The paginated list of saved quotes.

## 7. Authentication Flow
1. User visits `/` and is intercepted by the route guard.
2. User is redirected to `/login`.
3. User enters credentials; frontend submits `POST /api/auth/login`.
4. On success, the backend returns a JSON payload containing an `access_token`.
5. The token is saved to the client (see JWT Handling).
6. The frontend immediately calls `GET /api/users/me` with the token to retrieve the user's `role_tier` and identity.
7. The user is redirected to the `/` Dashboard.

## 8. JWT Handling
- **Storage:** The `access_token` will be stored in `localStorage` (or `sessionStorage`) to persist sessions across reloads.
- **Injection:** The centralized `fetch` wrapper will read the token and append `Authorization: Bearer <token>` to all protected API calls.
- **Expiration/Revocation:** If any API request returns an HTTP `401 Unauthorized`, the fetch wrapper will automatically clear the local token and redirect the user to `/login`.

## 9. API Client
Instead of installing Axios, a native `apiClient.js` module will be implemented.
It will feature:
- Base URL configuration (e.g., `/api`).
- Automatic inclusion of `Content-Type: application/json`.
- Automatic inclusion of the Authorization header.
- Standardized error throwing so components can safely `try/catch` network failures.

## 10. Login UI
The Login screen will consist of:
- A clean, centered card design.
- Email and Password input fields.
- A submit button with a "Loading..." disabled state.
- A prominent error banner to display invalid credential messages or network errors (handled natively via the backend's `401`/`400` responses).

## 11. Application Layout
Protected routes will be rendered inside an `AppLayout` component.
- **Header:** Displays the application title ("Benchmark Quote Generation Tool").
- **Navigation:** Links to "Dashboard" and "Quotes".
- **User Menu:** Displays the logged-in user's email and Role Tier (fetched from `/api/users/me`), alongside a "Logout" button.

## 12. Dashboard
The Dashboard (`/`) will serve as the initial authenticated view.
- Displays a welcoming message ("Welcome back, [Email]").
- Provides clear navigational pathways to the Quote List.
- Contains no invented business metrics or charts, serving solely as a structural anchor until future phases define dashboard analytics.

## 13. Quote List
The Quote List (`/quotes`) integrates with `GET /api/quotes`.
- **Data Display:** Renders a standard HTML table displaying:
  - Client Name
  - Region ID (Mapped to Region string if available, or raw ID)
  - Quote Generated Date (formatted from `created_at` or `date`)
  - Status
- **Loading State:** Displays a skeleton or spinner while `fetch` is pending.
- **Empty State:** Displays a friendly "No quotes found" message if the array is empty.
- **Data Restriction:** Strictly avoids rendering Cost or Margin data. The backend `QuoteSummary` schema does not provide this data, enforcing secure boundaries.

## 14. Search
- The Quote List will feature a "Search by Client Name" text input.
- Submitting the search appends the `client_name` query parameter to the `GET /api/quotes` request.
- The UI will reset pagination to page 1 upon initiating a new search.

## 15. Pagination
- The Quote List will utilize the backend's `skip` and `limit` query parameters.
- Standard "Previous" and "Next" buttons will adjust the local `skip` state (e.g., incrementing by `limit` size).
- If the returned array length is less than the `limit`, the "Next" button will be disabled.

## 16. Role-aware UI behavior
- The frontend will utilize the `role_tier` returned from `GET /api/users/me`.
- While CP7 focuses on quotes (which all roles can access, though Sales only sees their own), the frontend layout will conditionally render future navigational elements (like "Catalog" or "Admin Settings") based on this tier.
- *Crucially:* This is strictly for User Experience (UX).

## 17. Error Handling
- Component-level `try/catch` blocks will handle standard API rejections, displaying inline error states (e.g., "Failed to load quotes. Please try again.").
- Network disconnections or `500 Internal Server Error` responses will be caught gracefully without crashing the React application.

## 18. Security
- **JWT Lifecycle:** Tokens are cleared from storage upon explicit logout or a `401` backend response.
- **Protected Routes:** The React Router configuration prevents mounting protected components if the auth context lacks a valid token.
- **Frontend Role Handling:** Documented firmly as a UX convenience. The frontend assumes a malicious user can modify the local `role_tier` state, relying entirely on the backend to enforce `403 Forbidden` and `404 Not Found` for unauthorized data.

## 19. Testing Strategy
- Since test frameworks (e.g., Jest/React Testing Library) are not explicitly required for this scaffolding phase, CP7 validation will rely on manual user acceptance testing (UAT).
- Testing steps include verifying successful login, verifying protection of `/quotes` against unauthenticated access, ensuring Sales roles see only their quotes (via backend filtering), and confirming pagination/search API calls mutate the URL correctly.

## 20. Acceptance Criteria
1. The frontend starts successfully using standard React tooling.
2. A user can log in with valid backend credentials and receive a JWT.
3. A user cannot access `/quotes` or `/` without logging in.
4. The application header displays the user's role.
5. `GET /api/quotes` is successfully called and rendered in a table.
6. The Quote List handles search, pagination, loading, and empty states.
7. Logout successfully destroys the session and returns the user to `/login`.

## 21. Definition of Done
- The CP7 design specification is approved.
- The React frontend code is merged into `main`.
- No backend code is modified to support the frontend.
- All acceptance criteria are met.

## 22. Out of Scope
The following are strictly banned or deferred from CP7:
- AI requirement parsing and provider integrations.
- Microsoft Entra ID / SSO.
- Requirement Excel import/export.
- Schematic/block diagram generation.
- PDF generation.
- Quote Creation/Editing UI (Wizard).
- Admin Configuration UI.
- Any backend database changes.
- TypeScript, Tailwind CSS, shadcn, or Material UI.
- State management libraries like Redux.

## 23. Future Phase Candidates
- **CP8:** Quote Creation UI (Integration with Requirement/Pricing Engines).
- **CP9:** Quote Editing and Versioning UI.
- **CP10:** Catalog Management UI.
- **CP11:** Admin & System Configuration UI.
- **CP12:** Entra ID SSO Integration.
