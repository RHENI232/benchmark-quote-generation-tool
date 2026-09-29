# Pricing & Calculation Rules — WTVision Graphics Solution

Source of truth: WTVision_Requirements_v3.4, Section 4. These rules are
validated against a working prototype (8 rounds of revision, including a
real bug fix). Do not modify these formulas without confirming with the
business owner — they are not guesses.

A "line item" = one BOM row: Part Number, Quantity, Unit Price (looked up
from the catalog at that Part Number).

**Scope note:** Only the sections below (4.1–4.9) drive automatic BOM
calculation. Any other catalog part (e.g. most of MAM's reference items,
Professional Services) is a pricing-reference item only and is never
auto-added to a quote.

**Calculation order:** Sections 4.1–4.8 can be computed in any order.
Section 4.9 (Support) MUST be computed last — it depends on the totals of
everything else.

---

## 4.1 Ingest
**Condition:** "SDI Production Ingest" selected AND Ingest Channels > 0.

| Part Number | Quantity Formula | Description |
|---|---|---|
| MT1010 | ⌈Channels ÷ 4⌉ | Base unit, 1 per box of up to 4 channels |
| MT1011 | Channels − ⌈Channels ÷ 4⌉ | Each extra channel beyond the first in its box |
| MT1020 | Channels (1:1) | Trimmer, one per channel |
| BDLKDVQD2 *(Ingest variant)* | ⌈Channels ÷ 4⌉ | Ingest Capture Card (4-channel) |
| INGSVR101 | ⌈Channels ÷ 4⌉ | Ingest Server hardware, one per box |

> Worked example: 8 channels → 2× MT1010, 6× MT1011, 8× MT1020, 2× BDLKDVQD2, 2× INGSVR101.

⚠️ **BDLKDVQD2 is used by TWO different catalog rows** — one here (Ingest
Capture Card) and one in Section 4.5.1 (Graphics IO card). Same displayed
Part Number text, different description/price. Model as two distinct
internal catalog rows.

---

## 4.2 MAM (Media Asset Management)
**Condition:** "MAM" selected directly, OR "Production Playout" selected (which forces MAM on).

| Part Number | Quantity Formula | Description |
|---|---|---|
| MM1000 | 1 (flat) | wTVision Media Manager, includes 1 Media Agent |
| MA1001 | Number of Studios | Extra Locations/Media Agents, one per studio |
| MAMSVR101 | 1 (flat) | MAM Server hardware |

---

## 4.3 Production Playout
**Condition:** "Production Playout" selected. Also forces MAM on (4.2).

| Part Number | Quantity Formula | Description |
|---|---|---|
| MP0001 | 1 (flat) | wTVision Media Server, Single Channel FHD |
| MP0012 | 1 (flat) | First Input Manager |

**Dependency:** if MP0001 qty > 0 anywhere on the quote → Section 4.4 auto-adds 1× PL1004.

---

## 4.4 Playout Controller
"Control Clients" is entered per-studio, then **summed across all studios into one total** for this section.

| Part Number | Quantity Formula | Description |
|---|---|---|
| SC1000 | Sum of Control Clients (all studios) | Studio CG — central control app |
| STDCG101 | Same as SC1000 | Studio CG Control PC hardware |
| PL1001 | Same as SC1000 | R³ Engine Plugin for Studio CG |
| PL1004 | 1, only if MP0001 qty > 0 elsewhere on quote | Media Server Controller Plugin (auto-dependency) |

> **Do not double-count:** LED Video Wall and VR-AR (Unreal) bundles already
> include 1× SC1000 and 1× DE1001 in their bundle price. Show this to the
> user as an informational note only — never auto-add it as a separate line.
> Any Control Clients/Designers the user enters are on top of the bundled ones.

---

## 4.5 Graphics Engine (computed per studio, then combined into one section)

### 4.5.1 Base rule — applies to every studio regardless of Studio Type
| Part Number | Quantity Formula | Condition |
|---|---|---|
| R30001 | Number of Engines (this studio) | Engines ≥ 1 |
| R3ENG101 | Same as R30001 | Whenever R30001 is added |
| BDLKDVQD2 *(Graphics IO variant)* | Same as R30001 | Whenever R30001 is added |
| R30010 | 1 | Dual Channel checked (only selectable if Engines ≥ 1) |
| R30020 | 1 | Extra Live Input checked (only selectable if Engines ≥ 1) |

### 4.5.2 LED Video Wall — independent of Number of Engines
| Part Number | Quantity Formula | Condition |
|---|---|---|
| wG4000 | 1 (flat) | LED Video Wall selected, LED Outputs = 4 |
| wG8000 | 1 (flat) | LED Video Wall selected, LED Outputs = 8 |
| vWALLENG101 | 1 (flat) | LED Video Wall selected (either output option) |
| BDLKDVQD2 *(Graphics IO)* | 1 if LED Outputs=4, 2 if LED Outputs=8 | LED Video Wall selected |

⚠️ Deliberately **NOT** scaled by Number of Engines — this was a real bug
that was fixed during validation. LED Video Wall is self-contained.

### 4.5.3 Studio Type = VR-AR (R3 Engine) — fixed single-camera bundle
| Part Number | Quantity Formula |
|---|---|
| R30001 | +1 (on top of 4.5.1's base amount for this studio) |
| R3ENG101 | +1 (companion) |
| BDLKDVQD2 *(Graphics IO)* | +1 (companion) |
| UE0002 | 1 |
| ARENG101 | 1 |

This studio type never uses a camera count — always a single fixed camera setup.

### 4.5.4 Studio Type = VR-AR (Unreal) — scalable, up to 3 cameras
"Number of Cameras" (1/2/3) is shown only for this studio type.

| Part Number | Quantity Formula |
|---|---|
| wV3000 | 1 (flat) — bundle covers up to 3 camera channels |
| IMMVRENG101 | Number of Cameras × 2 |
| BDLKHCPRO8K12GG2 | Number of Cameras (1:1) |

---

## 4.6 Designer Tools
**Condition:** quote-level "Number of Designers" > 0 (single quote-wide count, not per studio).

| Part Number | Quantity Formula | Description |
|---|---|---|
| DE1001 | Number of Designers | R³ Designer |
| R3DES101 | Same as DE1001 | R³ Designer Workstation hardware |

---

## 4.7 NRCS Integration
| Part Number | Quantity | Condition |
|---|---|---|
| MG1000 | 1 | News Production selected |
| NP1010 | 1 | News Production AND Journalists = 10 |
| NP1025 | 1 | News Production AND Journalists = 25 |
| NP1050 | 1 | News Production AND Journalists = 50 |
| MG1001 | 1 | MOS Redundancy selected (independent) |
| PW1000 | 1 | NRCS Graphics Preview selected (independent) |

Note: selecting MOS Redundancy or NRCS Graphics Preview auto-forces News
Production on, so MG1000 + the Journalist-tier part are always present
alongside MG1001 or PW1000.

---

## 4.8 NLE Plugin
| Part Number | Quantity | Condition |
|---|---|---|
| NLE105 | 1 | NLE Plugin selected AND NLE Seats = 5 |
| NLE110 | 1 | NLE Plugin selected AND NLE Seats = 10 |
| NLE115 | 1 | NLE Plugin selected AND NLE Seats = 15 |

---

## 4.9 3 Years Standard Support — CALCULATED LAST
**Condition:** "3 Years Standard Support" selected.

1. Sum (Quantity × Sell Price) for every line item across every other
   section whose catalog **Brand is exactly "wTVision"** (exclude
   third-party/hardware-vendor branded items).
2. Support Price = that sum × 30%.
3. Add one line item: Description "First 3 Years Support - Standard",
   Quantity 1, Sell Price = Support Price.
4. This line item has **0% margin** — Cost Price = Sell Price. This is
   the one exception to the 15% default margin rule below.

---

## 4.10 Pricing & Margin Rules (catalog-wide)
- Every catalog item has Sell Price (list/customer) and Cost Price (internal).
- New item's Cost Price defaults to **Sell Price × (1 − Default Margin)**,
  default 15%. Must be a UI-configurable setting, not hardcoded.
- Support line item (4.9) is the only exception: always 0% margin.
- Margin % = **(Sell − Cost) ÷ Sell × 100** — margin-on-sell, not markup-on-cost.
- Cost Price, once set, is NOT auto-recalculated when Sell Price changes
  or when the Default Margin setting later changes.

---

## Known Data Gaps (must be confirmed with vendor before go-live)
- **PCR-ENGINE** — no confirmed Part Number, removed from automated logic.
- **BDLKHCPRO8K12GG2** — placeholder description/price ("Capture Card — spec TBC", $0).
- No confirmed vendor Sell Price yet ($0 placeholder): BDLKDVQD2 (Graphics
  variant), INGSVR101, MAMSVR101, STDCG101, vWALLENG101, ARENG101,
  IMMVRENG101, R3DES101.
- **Unresolved duplicate codes** (kept as separate rows with a "verify
  code" note): PS1050 used for two different Professional Services items;
  R31050 used for two different Render Engine options; the 15-seat NLE
  bundle's source code was listed as NLE110 instead of a distinct NLE115.

## Not Included in v1
- Schematic/block diagram export — descoped, not part of this build.
