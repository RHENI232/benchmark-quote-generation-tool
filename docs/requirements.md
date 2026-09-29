**WTVision Multi-Solution Quote Generation Platform**

Software Requirements Document

*Presales Quote Automation Tool*

Prepared for: Benchmark Broadcast Systems (S) Pte Ltd

Document Version: 3.4

Status: Draft — Based on Validated Working Prototype

Table of Contents

Document Control

| **Field**       | **Detail**                                                                                                                                                                                                                                                     |
|-----------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Document Title  | Software Requirements Document – Multi-Solution Quote Generation Platform                                                                                                                                                                                      |
| Version         | 3.4                                                                                                                                                                                                                                                            |
| Status          | Draft, derived from a validated interactive prototype, extended with multi-Solution/multi-currency/RBAC/AI-capture scope, revised for RBAC tier simplification, per-file export gating, an interim manual FX-rate entry flow, and a Quote List & Search screen |
| Source of Truth | This document reflects the business rules and behaviour of the working HTML prototype (wtvision_quote_app_14.html), plus all documented revisions through v3.4                                                                                                 |
| Intended Use    | To brief and manage the build of a production version of this tool as an AI-assisted citizen-developer build                                                                                                                                                   |
| Intended Reader | Non-technical project owner / product manager (also the citizen developer for this build), and the AI coding assistant used to implement it                                                                                                                    |

1\. Introduction

1.1 Purpose

This document describes the functional requirements, business logic, and business rules for a production version of the WTVision Graphics Proposal Generator — a presales tool that lets Benchmark Broadcast Systems staff turn a customer's technical requirement into a priced, formatted quotation.

It is written to be actionable by a non-programmer: every section is specified in plain language, with tables and worked examples rather than code. It is written to be actionable directly by the business owner acting as an AI-assisted citizen developer — it is the brief that should be handed to an AI coding assistant, section by section, as the basis for the build.

1.2 Background

A working interactive prototype (a single-file HTML application, wtvision_quote_app_14.html) has already been built and iteratively refined directly against real Benchmark Broadcast Systems / wTVision pricing and business rules. That prototype remains the source of truth for the business rules in Section 4 — nothing there is speculative.

The prototype currently runs entirely in a single user's web browser, storing its data locally on that one device, in one currency, for one selling entity, with no user accounts. This document's core recommendation is to preserve all of the validated business logic while re-platforming it onto a proper multi-user, centrally-hosted architecture, using the prototype itself as the migration seed.

1.3 Scope

In scope for the production build described here:

- A platform capable of hosting more than one Solution (product line) — for example "WTVision Graphics", "OTT Platform", and "Complete TV Station" — each with its own requirement form, business rules, and catalog

- Capturing a customer's technical requirement through a guided form, driven by the selected Solution

- Capturing a requirement from free-form text — a customer email or rough sales notes — with AI-assisted extraction into the structured form, subject to mandatory human review

- Automatically computing the correct bill of materials (BOM) and pricing from that requirement, using the business rules in Section 4

- Managing the underlying product/pricing catalog per Solution, including cost price, a configurable default margin, and bulk update/create via Excel import

- A single Region/Country selection per quote that drives three things together: the display currency, the selling Legal Entity, and the applicable regional tax rule

- Two regions configured at launch — Singapore (USD, Benchmark Broadcast Systems (S) Pte Ltd, no regional tax) and India (INR, India GST) — with the underlying Region/Legal Entity/Tax data model built to be pluggable, so further regions can be added later by configuration, not by a code change

- Generating a polished, entity-branded quotation, plus an internal costing view

- Saving, retrieving, and re-editing past quotes

- Importing/exporting the requirement itself as a spreadsheet, to support offline requirement-gathering

- Role-based access control, delivered in two phases: Phase 1 — manually-created accounts provisioned by email invite; Phase 2 — users additionally provisioned from the company's Microsoft 365 / Entra ID directory, coexisting with Phase-1 manual accounts

Out of scope for this document:

- Contract/proposal e-signature workflow

- CRM integration

- Regions/currencies beyond Singapore (USD) and India (INR), and any tax regime beyond India GST, until confirmed as a business need — the architecture must not preclude adding one later without a code change

- The Professional Services line-item picker on the Requirement page (deferred by the business owner to a later phase; the pricing data already exists in the catalog)

1.4 Intended Audience

- The business owner / product manager commissioning the build — also the citizen developer implementing it

- The AI coding assistant used to implement the system, and any human collaborator who later maintains or extends the resulting codebase

- Whoever performs the pre-go-live security review recommended for the authentication and access-control logic

2\. Product Overview

2.1 What the System Does

A presales engineer enters a customer's technical requirement — number of studios, ingest channels, graphics engine configuration per studio, newsroom integration needs, and so on — into a structured form. The system automatically works out exactly which hardware and software line items that requirement implies, using the business rules in Section 4, prices them from a maintained catalog, and produces:

- A customer-facing quotation (sell price only), issued on the letterhead of the Legal Entity matched to the quote's selected Region

- An internal costing view (cost price and margin per line, and rolled up), always in the USD base currency regardless of the quote's Region, for consistent internal reporting

- A cost/margin tracking sheet broken down by product section and brand

2.2 Users / Personas

| **Persona**             | **Needs**                                                                                                                   |
|-------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| Presales Engineer       | Build an accurate quote quickly without needing to memorise pricing or bundling rules; avoid pricing errors                 |
| Sales Manager           | See margin and cost visibility before a quote goes to a customer                                                            |
| Pricing / Product Owner | Keep the product catalog and pricing current as vendor price lists change, without needing a developer                      |
| Finance / Tax Admin     | Keep each region's tax rule and each region's Legal Entity details (name, address, registration number) correct and current |
| Customer                | Receives a clear, professional, correctly itemised quotation, from the correct selling entity for their region              |

2.3 Current Prototype Status

The existing prototype is feature-complete against every rule in Section 4 and has been validated by the business owner across 8 rounds of revisions, including a same-day bug report and fix (a graphics-engine quantity bug tied to LED Video Wall). It is a single self-contained HTML file with no backend: all data (catalog, pricing, saved quotes) lives in that one browser's local storage and is not shared between users or devices; there is exactly one selling entity (Benchmark Broadcast Systems (S) Pte Ltd, hardcoded), one currency (USD), and no user accounts. This is the central limitation the production build must resolve.

3\. Functional Requirements

Requirements are numbered (FR-x) for traceability into test cases and acceptance sign-off.

3.1 Solution / Product Line Selection

The production platform must be able to host several distinct product lines side by side — for example a WTVision Graphics quote, an OTT Platform quote, and a Complete TV Station quote — without one being hardcoded into the application.

> **FR-1:** On starting a new quote, the user shall first choose a Solution from a configurable list (e.g., WTVision Graphics, OTT Platform, Complete TV Station).
>
> **FR-2:** Each Solution shall have its own independently configurable Requirement form (fields, sections, valid values), Business Rules (Section 4-style quantity formulas), and Catalog of parts.
>
> **FR-3:** Everything downstream of Solution selection — the Requirement form, the Catalog & Pricing screen, the live preview, and the export — shall be driven by the selected Solution's configuration, not by product-specific code.
>
> **FR-4:** An authorised Admin-tier user shall be able to define a new Solution's Requirement schema and Business Rules through a configuration interface.

3.2 Quote Details

> **FR-5:** The system shall capture, per quote: Client name, Quote Reference Number, Date, Attention (contact name), Description, Version, and the quote's selected Region/Country.
>
> **FR-6:** These fields shall appear on both the customer-facing quotation and the internal costing view.

3.3 Requirement Capture — Guided Form

3.3.1 Main Requirement (quote-level, not tied to a specific studio)

The fields below are the WTVision Graphics Solution's Requirement schema, carried forward from the validated prototype as a concrete example of what a Solution's configuration looks like.

| **Field**                | **Type**            | **Notes**                                                             |
|--------------------------|---------------------|-----------------------------------------------------------------------|
| Number of Studios        | Number, 1–12        | Determines how many per-studio configuration blocks are shown         |
| Number of Designers      | Number, 0+          | Drives Designer Tools line items (Section 4.6)                        |
| News Production          | Yes/No              | Auto-forced on if MOS Redundancy or NRCS Graphics Preview is selected |
| Journalists              | One of 10 / 25 / 50 | Only shown when News Production is selected                           |
| MOS Redundancy           | Yes/No              | Forces News Production on when selected                               |
| Avid/Adobe NLE Plugin    | Yes/No              | —                                                                     |
| NLE Seats                | One of 5 / 10 / 15  | Only shown when NLE Plugin is selected                                |
| NRCS Graphics Preview    | Yes/No              | Forces News Production on when selected                               |
| SDI Production Ingest    | Yes/No              | —                                                                     |
| Ingest Channels          | Number, 0+          | Only meaningful when SDI Production Ingest is selected                |
| Production Playout       | Yes/No              | Forces MAM on when selected                                           |
| MAM                      | Yes/No              | Locked ON (cannot be unchecked) while Production Playout is selected  |
| 3 Years Standard Support | Yes/No              | See Section 4.9 for pricing logic                                     |

3.3.2 Per-Studio Configuration (repeated once per studio, 1–12 studios)

| **Field**                 | **Type**                                              | **Notes**                                                                   |
|---------------------------|-------------------------------------------------------|-----------------------------------------------------------------------------|
| Studio Type               | One of: Real Set / VR-AR (R3 Engine) / VR-AR (Unreal) | Drives different graphics-engine bundles — see Section 4.5                  |
| Number of Cameras         | One of 1 / 2 / 3                                      | Shown only when Studio Type = VR-AR (Unreal)                                |
| LED Video Wall            | Yes/No                                                | Independent of Number of Engines — see Section 4.5                          |
| LED Outputs               | One of 4 / 8                                          | Shown only when LED Video Wall is selected                                  |
| Number of Engines         | Number, 0+                                            | Drives R³ Engine hardware count for this studio, independent of studio type |
| Dual Channel              | Yes/No                                                | Shown only when Number of Engines ≥ 1                                       |
| Extra Live Input          | Yes/No                                                | Shown only when Number of Engines ≥ 1                                       |
| Number of Control Clients | Number, 0+                                            | Drives Studio CG hardware/software count, aggregated across all studios     |

> **FR-7:** The system shall show/hide dependent fields based on the rules above in real time as the user edits the form (no page reload).
>
> **FR-8:** The system shall show an explanatory, non-blocking note when a selection implies a bundled component is already included in another line item's price, so the user does not double-add it.

3.4 Requirement Capture — Free Text / Email

A user shall be able to paste unstructured text — a customer email, a rough note taken on a sales call — and have the system propose a filled-in requirement.

> **FR-9:** The system shall provide a "Paste Free Text / Email" entry mode alongside the Guided Form, where a user pastes or types unstructured text describing the customer's needs.
>
> **FR-10:** The system shall send that text, together with the current Solution's Requirement schema, to an AI/LLM extraction service, and pre-fill the Guided Form with its best-effort interpretation.
>
> **FR-11:** Every AI-extracted field shall be clearly marked as a suggestion and shall remain fully editable; the system shall never generate a priced quote directly from unreviewed AI output — the user must land on and actively confirm the Guided Form before proceeding.
>
> **FR-11.1:** Before the Guided Form is pre-filled, the system shall show the user a plain-language summary of what it understood from the source text — for example, "2 studios: one Real Set with 6-channel SDI Ingest and MOS Redundancy, one VR-AR (Unreal); Production Playout selected; 3-Year Standard Support requested" — distinguishing fields it found an explicit instruction for from fields it is leaving at default per FR-12. From this summary the user shall either apply it (landing on FR-11's ordinary editable, unconfirmed Guided Form) or discard it and retry with revised source text; the Guided Form itself is not touched until the user chooses to apply the summary.
>
> **FR-12:** Where the source text does not mention a field at all, the system shall leave it at its normal default and, where practical, indicate that no explicit instruction was found.
>
> *Data handling note: customer emails may contain confidential commercial information. Before this feature is enabled, the chosen AI provider's data-handling terms must be reviewed and approved.*

3.5 Catalog & Pricing Management

> **FR-13:** The system shall maintain a catalog of parts, per Solution, each with: Part Number, Description, Brand, Sell (list) Price, and Cost Price.
>
> **FR-14:** Parts are grouped into two kinds: (a) Rule-Driven Parts, whose Part Number is fixed because the calculation engine looks them up by that exact code, and (b) Reference Parts, which are informational/pricing-reference only.
>
> **FR-15:** For Rule-Driven Parts, the Part Number shall not be editable; Description, Brand, Sell Price, and Cost Price shall be editable by an authorised user.
>
> **FR-16:** For Reference Parts, all fields including Part Number shall be editable, and users shall be able to add or remove Reference Parts within a section.
>
> **FR-17:** The system shall support bulk create/update of catalog items via Excel import; the system matches existing Part Numbers and updates them, and creates new Part Numbers as Reference Parts.
>
> **FR-18:** The system shall validate an imported catalog file's structure before applying it and shall reject the whole import with a clear, row-level error report rather than partially applying a bad file.
>
> **FR-19:** The default margin percentage used to compute a new catalog item's Cost Price from its Sell Price shall be configurable in the UI by an authorised Catalog Entry (or higher-tier) user, not hardcoded. The prototype's validated value (15%) shall ship as the default setting. This setting may optionally be overridden per Solution.
>
> **FR-20:** The system shall provide a "Reset to Defaults" action that restores a Solution's catalog to its shipped starting values (with a confirmation step).
>
> **FR-20.1:** The Catalog & Pricing screen shall provide a full-text search box that, by default, matches against Part Number, Description, and Brand simultaneously, with an optional scope filter to narrow a search to a single field. A match shall filter the catalog view down to only the matching items and the section headers they belong to, rather than merely highlighting matches within an unfiltered list.

3.6 Automated Quote Generation Engine

> **FR-21:** On every change to the Requirement form, the system shall recompute the full bill of materials and re-render the live preview, using the selected Solution's Business Rules (Section 4).
>
> **FR-22:** The system shall omit any product section that has zero line items from both the live preview and the exported quotation.
>
> **FR-23:** Each computed line item shall retain a reference to the exact catalog Part Number it was generated from, so a later catalog price change is reflected the next time the quote is (re)computed.

3.7 Region-Driven Currency, Legal Entity & Tax

A quote carries a single Region/Country selection, and the display currency, the selling Legal Entity (the name/address/registration number printed on the quote letterhead), and the applicable tax rule are all derived together from that one selection — because in practice these three things always travel together (an India-region quote is issued in INR, from the India entity, with India GST; a Singapore-region quote is issued in USD, from the Singapore entity, with no regional tax).

> **FR-24:** Each quote shall have a selected Region/Country. The system shall derive that quote's Display Currency, Selling Legal Entity, and Tax Rule from a single Region configuration record rather than the user choosing currency, entity, and tax independently.
>
> **FR-24.1:** At launch, two Region records shall be configured: (a) Singapore — Currency USD, Legal Entity "Benchmark Broadcast Systems (S) Pte Ltd" (existing registration number and Singapore address), no regional tax; (b) India — Currency INR, an Indian selling entity (name, address, and GSTIN to be confirmed with Finance), Tax Rule = India GST.
>
> **FR-24.2:** The Region → Currency / Legal Entity / Tax mapping shall be maintained in an admin-editable configuration table, owned by a Management-tier (or Admin) user, so that a further region can be added later purely by configuration. No region-specific logic is to be hardcoded into the calculation or export engine.
>
> **FR-24.3:** Changing a quote's Region after other fields have been entered shall prompt the user for confirmation, since doing so simultaneously changes the display currency, the letterhead entity, and the applicable tax.
>
> **FR-25:** For any Region whose Currency differs from the catalog's USD base currency, the system shall retrieve foreign-exchange rates from the XE Currency Data API (xe.com) and cache them, refreshing on a schedule (e.g., daily) or on manual request. The rate used and its as-of date/time shall be shown on the quote for transparency and audit.
>
> **FR-25.1:** Until an XE Currency Data API subscription is procured, an authorised Management-tier (or Admin) user shall be able to manually enter the FX rate for a currency pair via the Region admin screen, recorded in the same Rate/As-Of fields a live XE lookup would populate.
>
> **FR-26:** If the XE service is unavailable at the time a rate is needed, the system shall fall back to the last successfully retrieved rate and visibly flag it as stale, rather than blocking quote generation.
>
> **FR-27:** The system shall support a configurable tax rule per Region (initially: India GST for the India region, no tax for the Singapore region) that an authorised Management-tier (or Admin) user can enable and set the rate for. When a Region's tax is enabled, tax shall be shown as a separate summary line, not blended into item prices.
>
> **FR-27.1:** Each Region's Legal Entity record shall carry Legal Entity Name, Registration/Tax ID Number, Address, and Contact Details, used to populate the Customer Copy letterhead — replacing the single hardcoded company block in the current prototype.
>
> **FR-28:** Tax logic beyond a single configurable percentage per Region (e.g., CGST/SGST vs. IGST splits, export exemptions, reverse charge) is out of scope for the first release and should be confirmed with the company's finance/tax advisor before go-live. The design shall not preclude adding this detail later.

3.8 Quote Export

> **FR-29:** The system shall export the current quote as three separate downloadable spreadsheet files rather than one workbook, since a downloaded file cannot enforce a per-sheet permission once it has left the server: (1) Customer Copy — sell price only, in the quote's Region-derived Legal Entity letterhead format, in the quote's Region-derived display currency, downloadable by anyone who can view the quote; (2) Internal — the same line items plus Cost Price, Total Cost, and Margin %, always in the base currency (USD) regardless of the quote's Region, downloadable only by a Management-tier (or Admin) user; (3) Tracking Sheet — cost and sell totals rolled up by product section and brand, downloadable only by a Management-tier (or Admin) user.
>
> **FR-30:** The Internal and Tracking Sheet files shall compute Margin % as (Sell − Cost) ÷ Sell × 100, guarded against division by zero.
>
> **FR-31:** Each exported file shall preserve Excel formulas (SUM, multiplication, margin) rather than static numbers, so a reviewer can audit or adjust it in Excel.
>
> **FR-32:** Each product section in an export shall be visually separated by a blank gap for readability.
>
> **FR-33:** The Internal and Tracking Sheet downloads shall be restricted to a Management-tier (or Admin) user, both server-side (returning 403 to anyone else) and, as a UX nicety, by hiding the buttons client-side.

3.9 Quote History

> **FR-34:** The system shall let a user save the current quote (header fields + full requirement + Solution + Region) under a name/reference, list previously saved quotes, reload one for editing, re-export one to Excel, or delete one.
>
> **FR-35:** Saved quotes shall be reloadable exactly as saved, including per-studio configuration.
>
> **FR-36:** Each saved quote shall record who created and who last edited it, for accountability now that the system is multi-user — this holds regardless of whether that user is a Phase-1 manual account or a Phase-2 Entra-synced account.
>
> **FR-34.1:** The saved-quote list required by FR-34 shall show, for every quote the caller is permitted to see, a running row number, Client Name, Region/Country, and Quote Generated Date, with a search box matching Client Name. A Sales-tier user shall see only quotes they own; every other tier (Catalog Entry, Management, Admin) shall see every saved quote regardless of owner.

3.10 Requirement Import/Export

> **FR-37:** The system shall export the current Requirement (Main Requirement fields plus the full per-studio table) as a spreadsheet, independent of the priced quotation export in FR-29.
>
> **FR-38:** Every field in the exported Requirement sheet that has a fixed set of valid values shall be constrained with a dropdown (data validation) in the spreadsheet.
>
> **FR-39:** Fields with a fixed enumeration shall use strict validation that rejects an out-of-list entry. Genuinely open-ended counts shall use a suggested-values dropdown that warns but does not block an out-of-list entry.
>
> **FR-40:** The system shall parse an imported Requirement sheet by field label, not by fixed cell position.
>
> **FR-41:** On import, the system shall validate Studio Type against the allowed values for the current Solution and reject/ignore anything else, falling back to a safe default.

3.11 User Account Management & RBAC

Users are added manually and authenticate with an emailed invite and a self-chosen password, with Microsoft 365 / Entra ID SSO and directory sync layered on later (Phase 2) without displacing Phase-1 accounts.

Phase 1 — Manual Accounts

> **FR-42:** An Admin-tier user (or a delegated User Admin) shall be able to add a user manually by entering their email address and assigning exactly one of the four role tiers (Sales / Catalog Entry / Management / Admin).
>
> **FR-43:** On adding a manual user, the system shall send that person a secure, time-limited email invite link; following it, the user sets their own password — no password is ever set or visible to the admin who created the account.
>
> **FR-44:** Passwords for manual accounts shall be stored using an industry-standard hashing algorithm (e.g., bcrypt or argon2) and never stored or displayed in plaintext, and never emailed.
>
> **FR-45:** A self-service "forgot password" flow shall be available for manual accounts, sending a fresh time-limited reset link to the account's registered email.
>
> **FR-46:** An Admin-tier user shall be able to disable, re-enable, or permanently delete a manual account, and to change its assigned tier.
>
> **FR-46.1:** The system shall refuse any action — disabling, deleting, or re-tiering an account — that would leave zero enabled Admin-tier accounts, returning a clear error rather than silently locking every administrator out.

Phase 2 — Microsoft 365 / Entra ID

> **FR-47:** The system shall additionally support Microsoft 365 / Entra ID as an identity provider: Single Sign-On login, and periodic synchronisation of users and, where practical, security-group membership, via the Microsoft Graph API.
>
> **FR-48:** Manual (Phase-1) accounts and Entra-synced (Phase-2) accounts shall be able to coexist. If a manual account's email address matches an account later synced from Entra ID, the system shall link them into a single user record — preserving that user's quote history, ownership, and role assignments — rather than creating a duplicate.
>
> **FR-49:** A manual account shall remain usable after Phase 2 goes live for anyone not present in the company's Microsoft 365 tenant (e.g., an external contractor), at Admin-tier discretion; an Admin-tier user may also convert a user to Entra-only, disabling their local password.

3.12 Schematic Diagram Export

Scoped deliberately to a functional/logical block diagram — one box per product section (and per studio where a section repeats per studio), with arrows for the relationships already implied by the Business Rules. A detailed signal-flow schematic or a physical/rack layout is a different, much larger undertaking that this feature does not attempt.

> **FR-50:** The system shall be able to generate a functional block diagram from a quote's computed BOQ: one box per visible product section, and one repeated sub-block per studio for sections that vary per studio (e.g., Graphics Engine), each labeled with its key quantities and Part Numbers.
>
> **FR-51:** Each Solution shall define a Connectivity Map alongside its Business Rules: a set of generic signal/control-flow relationships between its sections — e.g., for WTVision Graphics, SDI Sources → Ingest → MAM → Production Playout; NRCS/MOS Gateway → Studio CG → Graphics Engine (per studio); Studio CG → Media Server Controller when Production Playout is present. The Connectivity Map is maintained by an Admin-tier user.
>
> **FR-52:** The diagram shall omit any section or per-studio sub-block with zero line items, consistent with FR-22's existing rule for the BOQ itself, and shall omit any connection whose Connectivity Map entry has an unmet condition.
>
> **FR-53:** The diagram shall be available as a standalone downloadable file (e.g., SVG, PNG, or PDF) generated for the current quote, offered alongside — but separate from — the Excel exports.
>
> **FR-54:** Diagram generation is explicitly scoped to a functional/logical block diagram. A detailed signal-flow schematic (interface types such as SDI/IP/NDI, port counts, cabling, redundancy paths) or a physical/rack layout diagram is out of scope.

4\. Business Rules & Calculation Logic

Every rule below has been implemented and validated in the working prototype for the WTVision Graphics Solution specifically. This section should be treated as the authoritative specification for WTVision Graphics — more authoritative than any earlier verbal or emailed description, since it reflects the final, corrected state after real bugs were found and fixed against it.

Throughout this section, "line item" means one row of the bill of materials: a Part Number, quantity, and the unit price/cost looked up from the catalog at that Part Number.

4.1 Ingest

Applies only when "SDI Production Ingest" is selected and Ingest Channels \> 0.

| **Part Number** | **Quantity Formula**                               | **Description**                                       |
|-----------------|----------------------------------------------------|-------------------------------------------------------|
| MT1010          | ⌈Channels ÷ 4⌉ (one per "box" of up to 4 channels) | Ingest – base unit, 1 per box                         |
| MT1011          | Channels − ⌈Channels ÷ 4⌉                          | Each extra ingest channel beyond the first in its box |
| MT1020          | Channels (1:1)                                     | Trimmer, one per channel                              |
| BDLKDVQD2       | ⌈Channels ÷ 4⌉                                     | Ingest Capture Card (4-channel) — hardware            |
| INGSVR101       | ⌈Channels ÷ 4⌉                                     | Ingest Server hardware, one per box                   |

> *Worked example: 8 channels → 2× MT1010, 6× MT1011, 8× MT1020, 2× BDLKDVQD2, 2× INGSVR101.*

4.2 MAM (Media Asset Management)

Applies when "MAM" is selected directly, OR whenever "Production Playout" is selected (Production Playout forces MAM on).

| **Part Number** | **Quantity Formula** | **Description**                                |
|-----------------|----------------------|------------------------------------------------|
| MM1000          | 1 (flat)             | wTVision Media Manager, includes 1 Media Agent |
| MA1001          | Number of Studios    | Extra Locations/Media Agents, one per studio   |
| MAMSVR101       | 1 (flat)             | MAM Server hardware                            |

4.3 Production Playout

Applies when "Production Playout" is selected. Also forces MAM on (Section 4.2).

| **Part Number** | **Quantity Formula** | **Description**                                      |
|-----------------|----------------------|------------------------------------------------------|
| MP0001          | 1 (flat)             | wTVision Media Server, Single Channel FHD            |
| MP0012          | 1 (flat)             | First Input Manager (adds 1st input to Media Server) |

> *Dependency: if MP0001 is present anywhere on the quote (quantity \> 0), the Playout Controller section (4.4) automatically adds 1× PL1004.*

4.4 Playout Controller

"Control Clients" is a per-studio number, summed across all studios into a single total for this section.

| **Part Number** | **Quantity Formula**                                   | **Description**                                             |
|-----------------|--------------------------------------------------------|-------------------------------------------------------------|
| SC1000          | Sum of Control Clients across all studios              | Studio CG — central control application, per Control Client |
| STDCG101        | Same as SC1000                                         | Studio CG Control PC hardware, per Control Client           |
| PL1001          | Same as SC1000                                         | R³ Engine Plugin for Studio CG, per Control Client          |
| PL1004          | 1, only if MP0001 quantity \> 0 elsewhere on the quote | Media Server Controller Plugin (auto-dependency, see 4.3)   |

> *Note: LED Video Wall and VR-AR (Unreal) bundles already include 1× Studio CG (SC1000) and 1× R³ Designer (DE1001) in their bundle price. This is shown to the user as an informational note only — it is deliberately NOT auto-added as a separate line item, to avoid double-counting. Any Control Clients / Designers entered are treated as being on top of what is bundled.*

4.5 Graphics Engine (computed per studio, then combined into one section)

4.5.1 Base rule — applies to every studio regardless of Studio Type

| **Part Number**                      | **Quantity Formula**                  | **Condition**                                               |
|--------------------------------------|---------------------------------------|-------------------------------------------------------------|
| R30001                               | Number of Engines (this studio)       | Number of Engines ≥ 1                                       |
| R3ENG101                             | Same as R30001 (always 1:1 companion) | Whenever R30001 is added, for any reason                    |
| BDLKDVQD2 (Graphics IO card variant) | Same as R30001                        | Whenever R30001 is added, for any reason                    |
| R30010                               | 1                                     | Dual Channel checked (only selectable once Engines ≥ 1)     |
| R30020                               | 1                                     | Extra Live Input checked (only selectable once Engines ≥ 1) |

> *Important: the catalog Part Number "BDLKDVQD2" is shared by two different catalog entries with different descriptions and independent pricing: "Ingest Capture Card (4-channel)" (Section 4.1) and "Graphics IO card" (this section). They must be modelled as two distinct catalog rows internally even though they display the same Part Number text on the quote.*

4.5.2 LED Video Wall (independent of Number of Engines)

| **Part Number**              | **Quantity Formula**                       | **Condition**                                  |
|------------------------------|--------------------------------------------|------------------------------------------------|
| wG4000                       | 1 (flat)                                   | LED Video Wall selected, LED Outputs = 4       |
| wG8000                       | 1 (flat)                                   | LED Video Wall selected, LED Outputs = 8       |
| vWALLENG101                  | 1 (flat)                                   | LED Video Wall selected (either output option) |
| BDLKDVQD2 (Graphics IO card) | 1 if LED Outputs = 4, 2 if LED Outputs = 8 | LED Video Wall selected                        |

> *This is deliberately NOT scaled by Number of Engines — that was an earlier defect, corrected during validation: LED Video Wall is a self-contained selection.*

4.5.3 Studio Type = VR-AR (R3 Engine) — fixed, single-camera bundle

| **Part Number**              | **Quantity Formula**                                         |
|------------------------------|--------------------------------------------------------------|
| R30001                       | +1 (on top of the base Section 4.5.1 amount for this studio) |
| R3ENG101                     | +1 (companion of the above)                                  |
| BDLKDVQD2 (Graphics IO card) | +1 (companion of the above)                                  |
| UE0002                       | 1                                                            |
| ARENG101                     | 1                                                            |

> *This studio type never uses a camera count — it is always treated as a single fixed camera setup.*

4.5.4 Studio Type = VR-AR (Unreal) — scalable bundle, up to 3 cameras

A "Number of Cameras" field (1, 2, or 3) is shown only for this studio type.

| **Part Number**  | **Quantity Formula**                                                   |
|------------------|------------------------------------------------------------------------|
| wV3000           | 1 (flat) — already priced as a bundle covering up to 3 camera channels |
| IMMVRENG101      | Number of Cameras × 2                                                  |
| BDLKHCPRO8K12GG2 | Number of Cameras (1:1)                                                |

4.6 Designer Tools

Applies when the quote-level "Number of Designers" field is greater than 0 (this is a single quote-wide count, not per studio).

| **Part Number** | **Quantity Formula** | **Description**                                              |
|-----------------|----------------------|--------------------------------------------------------------|
| DE1001          | Number of Designers  | R³ Designer — 3D graphics template design tool, per designer |
| R3DES101        | Same as DE1001       | R³ Designer Workstation hardware, per designer               |

4.7 NRCS Integration

| **Part Number** | **Quantity Formula** | **Condition**                                                             |
|-----------------|----------------------|---------------------------------------------------------------------------|
| MG1000          | 1                    | News Production selected                                                  |
| NP1010          | 1                    | News Production selected AND Journalists = 10                             |
| NP1025          | 1                    | News Production selected AND Journalists = 25                             |
| NP1050          | 1                    | News Production selected AND Journalists = 50                             |
| MG1001          | 1                    | MOS Redundancy selected (independent of News Production selection)        |
| PW1000          | 1                    | NRCS Graphics Preview selected (independent of News Production selection) |

> *Selecting MOS Redundancy or NRCS Graphics Preview automatically forces News Production on — so in practice MG1000 and the Journalist-tier part will always also be present whenever MG1001 or PW1000 are.*

4.8 NLE Plugin

| **Part Number** | **Quantity Formula** | **Condition**                          |
|-----------------|----------------------|----------------------------------------|
| NLE105          | 1                    | NLE Plugin selected AND NLE Seats = 5  |
| NLE110          | 1                    | NLE Plugin selected AND NLE Seats = 10 |
| NLE115          | 1                    | NLE Plugin selected AND NLE Seats = 15 |

4.9 3 Years Standard Support

Applies when "3 Years Standard Support" is selected. This is calculated last, after every other section, because it depends on their combined totals.

- Step 1: Sum (Quantity × Sell Price) for every line item on the quote, across every other section, whose catalog Brand is exactly "wTVision" (third-party and hardware-vendor branded items are excluded).

- Step 2: Support Price = that sum × 30%.

- Step 3: Add one line item: Description "First 3 Years Support - Standard", Quantity 1, Sell Price = the computed Support Price.

- Step 4: This line item carries no margin — its Cost Price is set equal to its Sell Price (0% margin), unlike every other catalog item which defaults to a 15% margin (Section 4.10).

4.10 Pricing & Margin Rules (catalog-wide)

- Every catalog item has a Sell Price (list/customer price) and a Cost Price (internal cost).

- When a new catalog item is created, Cost Price defaults to Sell Price × (1 − Default Margin), validated at 15%; per FR-19 this must be a UI-configurable setting, not a hardcoded constant.

- The Support line item (Section 4.9) is a deliberate exception: it always carries 0% margin, regardless of the Default Margin setting.

- Margin % is always calculated as (Sell Price − Cost Price) ÷ Sell Price × 100 — margin-on-sell-price, not markup-on-cost.

- Cost Price, once set, is independently editable and is NOT recalculated automatically when Sell Price changes, nor when the Default Margin setting is later changed.

4.11 Known Data Gaps (must be resolved before go-live)

The following items exist in the current catalog with placeholder pricing/description because the real vendor data was not available at the time of prototyping. They must be confirmed with the vendor before the production system is used for real customer quotes:

- PCR-ENGINE — no confirmed real part number exists yet for this concept; it was removed from the automated logic pending a real Part Number

- BDLKHCPRO8K12GG2 — description and price are placeholders ("Capture Card — spec TBC", \$0)

- BDLKDVQD2 (Graphics IO card variant), INGSVR101, MAMSVR101, STDCG101, vWALLENG101, ARENG101, IMMVRENG101, R3DES101 — hardware items with no confirmed vendor Sell Price yet (currently \$0)

- Two known duplicate-code issues in the source wTVision price lists were never fully resolved: PS1050 is used for two different Professional Services line items, R31050 is used for two different Render Engine options, and the 15-seat NLE bundle's source code was listed as NLE110 rather than a distinct NLE115. All three are kept as separate catalog rows with a "verify code" note.

5\. Roles & Access Control

Phase 1 launched with five fine-grained roles (Sales User, Pricing Admin, Finance/Tax Admin, Solution Admin, Super Admin). These are now presented and assigned as four business-facing tiers. Each tier is a strict superset of the one before it:

| **Tier**      | **Permissions**                                                                                                                                                                                                                                              |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Sales         | Builds and saves quotes; sees the Customer Copy export. No Cost Price/Margin visibility anywhere, no catalog editing.                                                                                                                                        |
| Catalog Entry | Everything Sales can do, plus editing catalog Sell/Cost Price, importing catalog updates (FR-17), and setting the Default Margin (FR-19). Still no Cost Price/Margin visibility on the Quote preview/saved quotes, and no Internal/Tracking Sheet downloads. |
| Management    | Everything Catalog Entry can do, plus Cost Price/Margin visibility on the Quote preview and saved quotes, the Internal and Tracking Sheet downloads (FR-33), and Region/Legal Entity/Currency/Tax configuration.                                             |
| Admin         | Everything Management can do, plus defining new Solutions, their Requirement Schema and Business Rules, Connectivity Maps, and full user/role administration (FR-42–FR-46.1).                                                                                |

6\. Non-Functional Requirements

6.1 Performance

> **NFR-1:** The live preview shall recompute and re-render within 1 second of any Requirement field change, for a quote with up to 12 studios.
>
> **NFR-2:** Excel export/import shall complete within 5 seconds for a typical quote (under ~150 line items).
>
> **NFR-11:** Catalog search (FR-20.1) shall return filtered results within roughly 300ms of a keystroke for a Solution's catalog at its expected size (a few hundred items). If a catalog grows well beyond that, the search should be backed by a database full-text index rather than a naive per-keystroke scan across every field.

6.2 Security & Data Privacy

> **NFR-3:** Only authenticated, authorised users may view or edit Cost Price, Margin %, or the catalog, regardless of whether their account is a Phase-1 manual account or a Phase-2 Entra-synced account.
>
> **NFR-4:** Customer names and quote contents are business-confidential and must be protected accordingly (access control, encrypted storage/transport).
>
> **NFR-9:** Manual-account passwords shall never be stored, logged, or transmitted in plaintext, and invite/reset tokens shall be single-use and time-limited (FR-43, FR-45). Given this is an AI-assisted, single-developer build, this logic specifically should receive a pre-go-live security review.

6.3 Browser/Platform Support

> **NFR-5:** The system shall support the latest two versions of Chrome and Edge at minimum, matching the prototype's tested environment.

6.4 Availability

> **NFR-6:** As a sales-critical tool, target availability should be agreed as part of hosting selection, balanced against what a citizen-developer-operated system can realistically support.

6.5 Maintainability & Extensibility

> **NFR-7:** The business rules in Section 4 have already changed 8 times during prototyping. The production calculation engine must be structured so a rule change can be made and tested without a full redeployment cycle.
>
> **NFR-8:** Catalog price/description changes must not require a developer — this is already true in the prototype and must remain true in production.
>
> **NFR-10:** Because the codebase is built and maintained by one citizen developer with an AI coding assistant rather than a team, code and configuration (Business Rules, Region/Entity/Tax mappings) should favour clarity and documentation over cleverness, so that a future maintainer can understand it without the original author present.

7\. Assumptions, Risks & Open Items

| **\#** | **Item**                                                                                                                                                                                        | **Type**             |
|--------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------|
| 1      | Several hardware Part Numbers have no confirmed vendor price yet (Section 4.11)                                                                                                                 | Risk                 |
| 2      | PCR-ENGINE has no confirmed Part Number and was removed from automated logic                                                                                                                    | Open Question        |
| 3      | Three duplicate vendor codes (PS1050, R31050, NLE110/115) were never conclusively resolved                                                                                                      | Risk                 |
| 4      | The Professional Services line-item picker is deferred and out of scope for this build                                                                                                          | Assumption           |
| 5      | Regions/currencies/tax beyond Singapore (USD), India (INR/GST) are out of scope for this phase, but the architecture must remain pluggable                                                      | Assumption           |
| 6      | Business rules have changed 8 times during prototyping and should be expected to continue evolving                                                                                              | Risk                 |
| 7      | The XE Currency Data API is a paid third-party dependency; an outage or lapsed subscription stops live FX updates (mitigated by FR-25.1's manual-entry interim and FR-26's stale-rate fallback) | Risk                 |
| 8      | Free-text requirement capture sends customer email/notes content to a third-party AI API and requires data-privacy review before enabling                                                       | Risk                 |
| 9      | Tax correctness (GST treatment, exemptions, reverse charge) is a finance/legal judgement, not a software one, and must be reviewed before go-live                                               | Risk                 |
| 10     | The India selling entity's Legal Entity details (registered name, address, GSTIN) were not available at the time of writing                                                                     | Open Question / Risk |
| 11     | A fully generic, no-code rules engine is a hard problem; the recommended formula-language approach assumes comfort with Excel-like expressions                                                  | Risk                 |
| 12     | An AI-assisted, single-person build has no independent professional code review by default; a focused security review of authentication and access-control logic is recommended before go-live  | Risk                 |
| 13     | Schematic diagram export is scoped to a functional/logical block diagram only, not a detailed signal-flow schematic or physical/rack layout                                                     | Assumption           |

8\. Glossary

| **Term**                                  | **Meaning**                                                                                                                                                                                            |
|-------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| BOM                                       | Bill of Materials — the full list of priced line items a quote is made of                                                                                                                              |
| Rule-Driven Part                          | A catalog item the calculation engine can add to a quote automatically, based on the Requirement; its Part Number is fixed                                                                             |
| Reference Part                            | A catalog item kept for pricing reference only; not currently added to a quote automatically                                                                                                           |
| Control Client                            | A Studio CG operator seat; summed across studios to size the Playout Controller section (Section 4.4)                                                                                                  |
| Margin %                                  | (Sell Price − Cost Price) ÷ Sell Price × 100                                                                                                                                                           |
| Customer Copy / Internal / Tracking Sheet | The three separately downloadable, independently role-gated export files (Section 3.8)                                                                                                                 |
| NRCS                                      | Newsroom Computer System — the newsroom software this tool's graphics systems integrate with                                                                                                           |
| MAM                                       | Media Asset Management                                                                                                                                                                                 |
| MOS                                       | Media Object Server protocol — the integration standard between newsroom and graphics/playout systems                                                                                                  |
| Region / Legal Entity                     | A configured Region/Country (e.g. Singapore, India) that determines a quote's display currency, letterhead-selling entity, and tax rule                                                                |
| Manual Account                            | A Phase-1 user account created directly in-app by an Admin-tier user, authenticated by an emailed invite and a self-chosen password                                                                    |
| Entra-Synced Account                      | A Phase-2 user account provisioned via Microsoft 365 / Entra ID directory sync and authenticated by company SSO                                                                                        |
| Citizen Developer (AI-Assisted)           | The business owner, building the production system by directing an AI coding assistant rather than hiring a professional developer                                                                     |
| Connectivity Map                          | A per-Solution set of generic signal/control-flow relationships between product sections, used to generate the schematic diagram export; does not exist yet and must be authored                       |
| Schematic Diagram Export                  | A downloadable functional/logical block diagram generated from a quote's BOQ and its Solution's Connectivity Map; explicitly not a detailed signal-flow or rack/physical layout                        |
| Requirement Summary (AI extraction)       | The plain-language, pre-Guided-Form recap of what the free-text/email AI extraction understood from the source text, which the user applies or discards before the Guided Form is pre-filled (FR-11.1) |
| Role Tier                                 | One of the four business-facing access levels (Sales, Catalog Entry, Management, Admin) a user is assigned; the original five fine-grained role names remain in use underneath as permission codes     |
| Quote List & Search                       | The searchable list of every saved quote a user is permitted to see, scoped by Role Tier (FR-34.1)                                                                                                     |
