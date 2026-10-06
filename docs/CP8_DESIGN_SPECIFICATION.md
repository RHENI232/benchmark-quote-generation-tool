# CP8 Design Specification: Quote Generation Workflow UI

## 1. Purpose
The purpose of CP8 is to implement the actual quote-generation workflow in the React frontend. It bridges the foundational UI established in CP7 with the complex business logic (pricing, BOM generation, requirements parsing) established in CP3, CP4, and CP5. The UI must remain a thin client, delegating all business rules, catalog lookups, pricing calculations, and requirement cascades to the backend FastAPI endpoints.

## 2. Current Repository State
- **Frontend**: React, standard JavaScript, standard CSS, Vite, React Router, Context API for Auth.
- **Backend**: FastAPI, PostgreSQL, SQLAlchemy.
- **Architecture**: Cleanly separated. Frontend handles presentation and JWT authentication; Backend handles all RBAC, pricing, and data persistence.

## 3. CP1-CP7 Dependency Summary
- **CP3/CP4/CP5**: Implemented `RequirementEngine` and `PricingEngine` which process abstract JSON requirements into concrete BOMLineSpecs, fetching catalog pricing, computing margins, and applying FX/Tax.
- **CP7**: Implemented the Application layout, AuthContext (JWT handling), ProtectedRoutes, Dashboard, and Quote List views.

## 4. Existing Backend APIs
The frontend will orchestrate the quote lifecycle using these existing APIs:
- `GET /api/solutions` - Fetches available solutions (ID, Name, Requirement Schema).
- `POST /api/quotes/preview` - Accepts `QuoteCreate` payload. Validates requirements, runs pricing engines, and returns a calculated `QuoteResponse` *without* saving to the database.
- `POST /api/quotes` - Accepts `QuoteCreate` payload. Creates and returns a `DRAFT` quote with an ID and generated Quote Reference.
- `PUT /api/quotes/{id}` - Updates header fields (Client Name, Attention, Description) of a DRAFT.
- `POST /api/quotes/{id}/recalculate` - Accepts updated requirements, runs engines, updates the DRAFT quote.
- `POST /api/quotes/{id}/save` - Transitions a DRAFT quote to SAVED (immutable) status.

## 5. Existing Quote Business Logic
The backend enforces the following authoritative logic flow:
1. **Requirements Parse**: `RequirementPayload` validates inputs (e.g., `number_of_studios`).
2. **Cascade**: Values automatically cascade (e.g., if `nrcs_graphics_preview = True`, `news_production` is forced to `True`).
3. **BOM Generation**: `parse_and_evaluate_requirements` translates rules into abstract `lookup_keys`.
4. **Pricing Generation**: `PricingEngine.calculate_and_save_quote()` takes the keys, queries the Catalog, applies FX rates, applies Tax rules, and computes subtotals.
5. **Support Calculation**: A 30% support fee (3 years) is automatically calculated based strictly on specific lines (wTVision brand items) and appended as an extra line item.

**CRITICAL**: The frontend MUST NOT duplicate any of this logic. It only collects the raw data and displays the resulting `QuoteResponse`.

## 6. Quote Generation Data Flow
`User Input -> Local React State -> POST /api/quotes/preview -> Display Response -> POST /api/quotes -> POST /api/quotes/{id}/save`

## 7. CP8 User Workflow
Given the complexity of the requirement inputs (specifically dynamic arrays of `studios`), the optimal UX is a **Multi-step Wizard**:
- **Step 1: Setup**: Select Region, Select Solution, Input Client Name, Attention, Description.
- **Step 2: Global Requirements**: Form for top-level toggles and drop-downs (News Production, NLE Seats, etc.).
- **Step 3: Studio Configurations**: Dynamically renders N forms based on `number_of_studios` entered in Step 2.
- **Step 4: Preview & Review**: Presents the fully calculated quote (via `/preview`).
- **Step 5: Finalization**: Options to "Save as Draft" or "Save as Final".

## 8. Screen Architecture
A new top-level route `/quotes/new` pointing to a `QuoteWizard` component.
- `QuoteWizard` (Parent container managing step state and data).
  - `QuoteSetupStep` (Form inputs).
  - `QuoteRequirementsStep` (Main toggles).
  - `QuoteStudiosStep` (Dynamic array of studio configurations).
  - `QuotePreviewStep` (Displays `QuoteResponse` tables).

## 9. Field Specification
The frontend must collect the following exactly matching the backend `RequirementPayload`:

**A. Headers** (Required for all quotes)
- `client_name` (String, Required)
- `attention` (String, Optional)
- `description` (String, Optional)
- `region_id` (Integer, Required)
- `solution_id` (Integer, Required)

**B. Global Requirements** (Inside `requirement_data`)
- `number_of_studios` (Number, 1-12)
- `number_of_designers` (Number, >= 0)
- `news_production` (Boolean)
- `journalists` (Enum: 10, 25, 50) - *Visible/Enabled only if News Production is true*
- `mos_redundancy` (Boolean)
- `nle_plugin` (Boolean)
- `nle_seats` (Enum: 5, 10, 15) - *Visible/Enabled only if NLE Plugin is true*
- `nrcs_graphics_preview` (Boolean)
- `sdi_production_ingest` (Boolean)
- `ingest_channels` (Number) - *Visible/Enabled only if SDI Ingest is true*
- `production_playout` (Boolean)
- `mam` (Boolean)
- `three_years_support` (Boolean)

**C. Studio Requirements** (Array of objects, inside `requirement_data.studios`)
- `studio_index` (Matches array index)
- `studio_type` (Enum: "Real Set", "VR-AR (R3 Engine)", "VR-AR (Unreal)")
- `number_of_cameras` (Number, 1-3) - *Only enabled if Studio Type is Unreal*
- `led_video_wall` (Boolean)
- `led_outputs` (Enum: 4, 8) - *Only enabled if LED Wall is true*
- `number_of_engines` (Number)
- `dual_channel` (Boolean) - *Requires engines > 0*
- `extra_live_input` (Boolean) - *Requires engines > 0*
- `number_of_control_clients` (Number)

## 10. API Integration Map
- Mount `/quotes/new`: `GET /api/solutions` (and `GET /api/regions` once fixed).
- Step 1->4 progression: Local state updates only.
- Render Step 4: Call `POST /api/quotes/preview` with current state.
- Click "Save Draft": Call `POST /api/quotes`. Redirect to `/quotes`.
- Click "Save Final": Call `POST /api/quotes` -> take returned `id` -> Call `POST /api/quotes/{id}/save`. Redirect to `/quotes`.

## 11. Frontend State Management
- Use standard React `useState` at the `QuoteWizard` container level.
- Define a single `draftQuote` object mapping exactly to `QuoteCreate` schema.
- **Refresh Protection**: Implement `localStorage.setItem('quote_wizard_backup', JSON.stringify(draftQuote))` via `useEffect`. Restore on mount if present. Clear on successful API save. No external state libraries (e.g., Redux) required.

## 12. Validation Strategy
- Use native HTML5 attributes (`required`, `min`, `max`).
- Implement basic client-side visibility toggles (e.g., hiding `nle_seats` if `nle_plugin` is false) for UX responsiveness.
- Rely on the backend's strict Pydantic `ValidationError` cascades to catch invalid states during the `/preview` call.

## 13. Error Handling
- Wrap API calls in `try/catch`.
- Catch backend 409 (RequirementEngineError/PricingEngineError/IntegrityError) and 422 (Validation) exceptions.
- Display a unified `ErrorBanner` component at the top of the wizard step indicating why calculation or saving failed.

## 14. RBAC/Security
- **Backend Enforced**: The `mask_quote_financials_for_sales` wrapper automatically strips `unit_cost_price_snapshot`, `line_cost_total`, `margin_percent`, and `subtotal_cost_usd` for Sales users.
- **Frontend Implementation**: The `QuotePreviewStep` must conditionally render cost/margin columns ONLY if those keys are present and not `undefined` in the returned `QuoteResponse`. The frontend does not verify the user's role to determine column visibility; it reacts to the data structure provided by the server.

## 15. Quote Preview
The Preview screen will render:
1. **Quote Headers**: Client Name, Region, Generated Date (Now).
2. **Line Items Table**: Columns for Part Number, Description, Brand, Qty, Unit Sell, Line Total Sell. (And Cost/Margin if provided).
3. **Financial Summary**:
   - Subtotal USD
   - Applied Tax Rate (%) -> Tax Amount
   - Applied FX Rate -> Total in Local Currency (Currency Code)
4. **Legal Entity info** (From Region data).

## 16. Save/Recovery Behavior
- **Backward/Forward Navigation**: Preserves React local state.
- **API Failure**: Remains on current step, displays error banner, preserves data.
- **Successful Save**: Local storage backup cleared, redirect to `/quotes`.
- **Double Save**: Prevented via `isSubmitting` UI lock state on buttons.

## 17. CP8 Scope
- UI Wizard for gathering requirements.
- Dynamic form visibility based on Solution schema (hardcoded mapped to WTVision for MVP).
- Previewing Quote via `/api/quotes/preview`.
- Saving DRAFT and SAVED quotes via `/api/quotes` endpoints.

## 18. Out of Scope
- Entra ID / Microsoft SSO integration.
- PDF / Excel export implementation (CP9/Future).
- AI requirement parsing (CP8+).
- Modifying Catalog pricing (CP10).

## 19. Backend Gaps Blocking CP8
- **Missing API (`GET /api/regions`)**:
  - *Why CP8 needs it*: The frontend `QuoteCreate` payload requires a valid `region_id`. Currently, there is no endpoint to fetch the list of available Regions (Country Name, ID) to populate the initial dropdown in Step 1.
  - *Existing related code*: `backend/app/models/region.py` contains the schema.
  - *Recommended Solution*: Implement a basic `GET /api/regions` endpoint in the backend that queries the `Region` table and returns a list. Must be accessible by all authenticated users. Requires backend modification.

## 20. Acceptance Criteria
1. User can navigate to a "New Quote" flow.
2. User can select Region and Solution.
3. User can input specific WTVision requirements and configure multiple studios.
4. UI hides/shows dependent fields based on boolean toggles.
5. User can view a fully calculated Preview of the quote before saving.
6. Sales tier users do not see cost/margin columns in the preview.
7. User can save the quote (Draft or Final) and return to the Dashboard.
8. Unsaved progress survives an accidental browser refresh via `localStorage`.
9. The backend remains the exclusive authority on pricing rules and requirement validations.

## 21. Testing Strategy
- Create manual test scripts verifying:
  - Wizard state preservation.
  - Correct API payload construction.
  - Conditional RBAC rendering of financial tables based on mocked Backend responses.
- Backend testing for the new `/api/regions` endpoint.

## 22. Definition of Done
- Specification reviewed and approved.
- Missing `GET /api/regions` gap resolved.
- UI components built using standard CSS and React.
- E2E Quote generation flow passes manually.

## 23. Recommended Implementation Order
1. **Backend**: Resolve the Gap (Implement `GET /api/regions`).
2. **Frontend UI**: Scaffold the `/quotes/new` route and the Multi-step container.
3. **Frontend Forms**: Implement the 3 data-entry steps (Setup, Requirements, Studios) matching `RequirementPayload`.
4. **Frontend API**: Connect local state to `POST /api/quotes/preview` and render the Preview step.
5. **Frontend Save**: Wire the "Save" buttons to `POST /api/quotes` and `/save`.
