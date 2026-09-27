# Phase 1B — Canonical Architecture Reconciliation

## Purpose

Reconcile Stocker's **actual existing data structures** before any schema rewrite or migration.

This document answers four questions for each persistent structure:

1. What is its purpose?
2. Is it raw, canonical, verified, derived, or cached?
3. Who writes it?
4. Who is allowed to treat it as authoritative?

This is a repository audit, not a proposed greenfield architecture.

## Executive finding

Stocker already contains more canonical architecture than the first Phase 1 audit recognized.

The current system has five meaningful layers:

```text
COMPANY IDENTITY
    company_registry
          |
          v
SOURCE / EVIDENCE
    source_documents
    document_pages_cache
    company_knowledge_facts
          |
          +---- financial_verification_records
          |
          v
FINANCIAL PAYLOAD / STATEMENTS
    stocks_cache
    FinancialStatement
          |
          v
DETERMINISTIC ANALYTICS
    financial_engine
          |
          v
PROJECTIONS / RANKING
    projection_engine
    ranking_engine
```

The architecture is therefore **not missing canonicalization**. It has a canonical identity layer and a meaningful verification/evidence layer, but the analytical engines have not yet been fully connected to those layers.

---

## 1. Existing structure map

| Structure | Current role | Classification | Current authority |
|---|---|---|---|
| `company_registry` | Canonical listed-company identity and universe membership | **Canonical identity** | Authoritative for company identity |
| `source_documents` | Discovered/validated filing/document catalog | **Source registry** | Authoritative document catalog |
| `document_pages_cache` | Extracted PDF page text | **Raw/derived source cache** | Not financial truth; source-processing cache |
| `company_knowledge_facts` | AI-extracted qualitative/operational facts with quote/page provenance | **Evidence layer** | Authoritative for persisted extracted evidence, subject to source/evidence validation |
| `financial_verification_records` | Screener vs official financial reconciliation | **Canonical verification layer** | Authoritative verification/reconciliation record |
| `stocks_cache` | Full Screener stock payload | **Raw/source snapshot cache** | Should not be treated as canonical analytical truth |
| `stocks_cache.json` | Legacy bootstrap/cache | **Legacy raw cache** | Should not be a second source of truth |
| `FinancialStatement` | In-memory typed representation of statement payload | **Transport/domain representation** | Not persistent authority |
| `financial_engine.py` | Deterministic financial calculations | **Derived analysis** | Authoritative for its defined calculations, given valid inputs |
| `projection_engine.py` | Forward assumptions, projections and valuation scenarios | **Model / assumptions** | Derived model output, never reported fact |
| `ranking_engine.py` | Composite score/verdict | **Derived decision layer** | Derived output; methodology must be explicit |
| `ai_analysis_cache` | Cached multi-document AI synthesis | **AI-derived cache** | Not source truth |
| `ai_document_summaries` | Cached document summaries | **AI-derived cache** | Not source truth |
| `document_sync_state` | Incremental source-check state | **Operational metadata** | Not evidence |

### Important correction

The existence of `financial_verification_records` means the previous statement:

> "There is no canonical financial fact layer"

was too broad.

The more precise statement is:

> **There is an existing canonical financial verification layer, but it is not yet the universal upstream authority consumed by deterministic analytics.**

---

## 2. Company identity — already strong

`company_registry` is the current canonical identity registry.

It contains:

- canonical symbol
- company name
- NSE symbol
- BSE code
- ISIN
- exchange
- sector / industry
- aliases
- active / universe status
- source and verification metadata

Identity matching follows:

1. ISIN
2. verified NSE symbol
3. BSE code
4. canonical symbol
5. exact company name

The implementation also contains source-precedence tiers and an authoritative identity upgrade path.

### Assessment

**KEEP.**

This is real canonical infrastructure and should become the identity anchor for every downstream record.

### Reform needed

Ensure downstream tables eventually reference a stable company identity rather than repeatedly treating `symbol` as the only identity key.

Do this carefully; it does **not** automatically justify a destructive schema rewrite.

---

## 3. Source documents — already strong foundation

`source_documents` stores:

- symbol
- title
- URL
- document type
- period/date
- discovery source
- actual source host
- validity
- added timestamp

This provides a persistent document catalog.

### Assessment

**KEEP and strengthen.**

The next maturity step is source-version awareness:

- document retrieval timestamp
- content hash where practical
- publication date vs retrieval date
- source authority
- superseded/replaced status

This becomes important for historical time-travel testing.

---

## 4. Qualitative evidence — one of the strongest existing pieces

`company_knowledge_facts` already stores:

- source document
- document type
- period
- category
- metric
- raw stated value
- numeric value
- unit
- target period
- scope
- claim type
- source quote
- source page
- extraction timestamp
- original fact JSON

This is already close to the evidence model Stocker needs.

### Assessment

**KEEP. Do not replace.**

Instead, clarify the distinction between:

- reported fact
- management guidance
- management claim
- AI interpretation
- derived interpretation

The `claim_type` field is the beginning of that distinction.

---

## 5. Financial verification — existing canonical reconciliation layer

`financial_verification_records` is keyed by:

```text
company
+ canonical_metric
+ canonical_period
+ scope
```

It records:

- Screener value
- official value
- variance
- verification status
- tolerance
- source URLs
- official source name
- official document ID
- notes
- verification timestamp

Current statuses include:

- VERIFIED
- DISCREPANCY
- NOT_COMPARABLE
- OFFICIAL_SOURCE_MISSING
- SCREENER_VALUE_MISSING
- INSUFFICIENT_EVIDENCE
- UNVERIFIED

### Assessment

**KEEP. This is a major existing asset.**

### Critical gap

The analytical engines do not yet universally consume these records.

Current pattern remains approximately:

```text
Screener
  -> stocks_cache
  -> FinancialStatement
  -> financial_engine
  -> projection/ranking
```

while verification operates more like:

```text
Screener + official filing
  -> financial_verification_records
  -> verification API/UI
```

These are two parallel paths.

### Reform

Move toward:

```text
source observations
      |
      v
verified/canonical financial representation
      |
      v
financial_engine
```

But first prove the mapping with a narrow vertical slice. Do not migrate the entire application at once.

---

## 6. stocks_cache — correctly classified as raw/cache, but currently overused

`stocks_cache` stores the full serialized stock payload.

This is useful for:

- avoiding repeated network fetches
- retaining the latest normalized Screener snapshot
- bootstrapping existing data
- backward compatibility

### Assessment

**KEEP temporarily as a raw/source snapshot cache.**

### Problem

It currently acts as more than a cache because the analytical pipeline hydrates `FinancialStatement` directly from it.

That makes it an accidental analytical source of truth.

### Reform

Explicitly establish:

> `stocks_cache` = raw/normalized provider snapshot, **not canonical financial truth**.

The analytical layer should eventually consume canonical verified facts, while the cache remains useful for ingestion/recovery.

---

## 7. stocks_cache.json — legacy duplication

The repository still contains the JSON cache and database bootstrapping can read it when seeding the company registry.

### Assessment

**Legacy compatibility only.**

It should not remain an independently authoritative store.

### Reform

Establish one-way migration:

```text
legacy JSON -> migration/bootstrap -> SQLite
```

not:

```text
JSON <-> SQLite
```

Retire it only after confirming no runtime path depends on it.

---

## 8. FinancialStatement / financial_engine

The `FinancialStatement` / `FinancialRow` structures are useful typed representations.

The deterministic financial engine already implements meaningful analysis including:

- CAGR
- quarterly QoQ/YoY growth
- historical margins
- effective tax rate
- CFO/PAT
- FCF
- capex derivation
- FCF confidence
- balance-sheet analysis
- DuPont-style calculations
- working-capital analysis

The FCF implementation explicitly distinguishes reported capex from balance-sheet-derived capex and attaches confidence/anomaly warnings.

### Assessment

**KEEP the calculation engine.**

### Reform

Change the input boundary, not the mathematics.

Instead of:

```text
FinancialStatement -> get_row_values() -> calculation
```

move toward:

```text
Canonical Financial Facts
        |
        v
typed analytical input
        |
        v
financial_engine
```

The engine should remain deterministic and independently testable.

---

## 9. Metric mapping is a real gap

`get_row_values()` currently performs exact matching and then fuzzy substring matching.

This is useful against provider variation but is not a sufficient canonical taxonomy.

Example problem:

```text
"Sales"
"Revenue"
"Revenue from Operations"
"Net Sales"
```

must map deliberately to a controlled canonical metric, not accidentally through substring behavior.

### Reform

Create a controlled metric dictionary/mapping layer:

```text
provider metric
      |
      v
canonical_metric
      |
      v
unit / scope / statement / sign convention
```

This should be **mapping infrastructure**, not a new duplicate financial fact store.

---

## 10. Scope and period normalization

Verification already carries:

- canonical period
- scope
- unit
- currency

The raw statement representation does not make these dimensions equally explicit at each fact level.

### Reform

The canonical analytical representation must always know:

- company
- metric
- period
- period type
- scope
- unit
- currency
- value
- source
- verification status

This is especially important for:

- consolidated vs standalone
- annual vs quarterly
- fiscal-year differences
- restatements
- source reconciliation
- time-travel testing

---

## 11. AI layer

The AI system has two distinct persistent outputs:

### Per-document

`ai_document_summaries`

### Multi-document synthesis

`ai_analysis_cache`

Both have provider/model/timestamp metadata.

### Assessment

**KEEP as caches, not truth.**

The more important evidence store is `company_knowledge_facts`.

The AI synthesis should be treated as a reproducible interpretation generated from source evidence, not as a replacement for that evidence.

---

## 12. Projection and ranking

The architecture currently has:

```text
financial data
    |
analytics
    |
projection
    |
ranking
    |
verdict
```

This is the area requiring the largest conceptual reform.

The engines currently combine:

- historical facts
- assumptions
- AI-derived evidence
- valuation assumptions
- composite scoring
- final investment verdict

without enough separation between these classes.

### Assessment

**Do not delete yet.**

The projection/ranking code is valuable existing work, but its role needs to change.

First establish:

```text
FACTS
  ↓
ANALYSIS
  ↓
ASSUMPTIONS
  ↓
PROJECTION
  ↓
VALUATION
  ↓
SCENARIOS
  ↓
INVESTMENT THESIS
```

The existing ranking engine should eventually become an opportunity-discovery layer rather than the application's fundamental truth engine.

---

## 13. Current authority matrix

### Authoritative

- Company identity → `company_registry`
- Source document identity → `source_documents`
- Verified financial reconciliation → `financial_verification_records`
- Persisted qualitative evidence → `company_knowledge_facts`
- Deterministic calculation definitions → `financial_engine.py`

### Non-authoritative / derived

- `stocks_cache`
- `stocks_cache.json`
- `FinancialStatement` hydrated payload
- `ai_analysis_cache`
- `ai_document_summaries`
- projections
- scenarios
- rankings
- investment verdicts

This distinction should become explicit in repository documentation and eventually encoded through interfaces/contracts.

---

## 14. Actual gap list after reconciliation

### P0 — Analytical pipeline bypasses existing verification architecture

The most important gap.

Canonical verification exists, but financial analytics still primarily start from the provider payload.

### P0 — Two physical financial caches

SQLite `stocks_cache` and JSON `stocks_cache.json` still coexist.

### P0 — No formal analytical snapshot/version boundary

A conclusion needs to be reproducible against the exact:

- source data
- verification state
- AI evidence version
- assumptions
- model version
- calculation version

This becomes essential for historical testing.

### P1 — Canonical metric taxonomy

Source labels need controlled mapping to canonical financial metrics.

### P1 — Fact/derivation contracts

The code needs explicit boundaries between reported facts, calculations, assumptions, projections and interpretations.

### P1 — Source/version identity

Documents and source payloads need stronger version/hash metadata for reproducibility.

### P1 — API/runtime architecture

The API still performs too much derived computation synchronously.

### P1 — Sector-specific analytical contracts

Current banking detection and model differentiation remain simplistic.

---

## 15. What we should NOT do now

Do not:

- create a second `financial_facts` table blindly
- rewrite `financial_engine.py` from scratch
- delete `stocks_cache` immediately
- replace all AI infrastructure
- tune ranking weights
- add more scoring factors
- add technical analysis
- redesign the entire UI
- migrate databases before proving the lineage slice

---

## 16. Verified-metric coverage finding

The existing `official_financial_service.py` confirms that Stocker already has a serious fail-closed canonical verification pipeline. However, its current `SAFE_CANONICAL_METRICS` is deliberately limited to:

- REVENUE
- PBT
- PAT
- BASIC_EPS
- DILUTED_EPS

This matters for the planned Revenue / PAT / CFO / FCF slice:

- **Revenue** → existing verified canonical path exists.
- **PAT** → existing verified canonical path exists.
- **CFO** → currently remains primarily a Screener statement fact; it is not covered by the official verification layer.
- **FCF** → currently is a Stocker-derived calculation from CFO minus capex; it is not a reported fact and should not be treated as one.

Therefore we should **not pretend all four metrics can immediately use the same canonical authority**. The correct architecture is to distinguish:

1. **Verified reported facts** — e.g. Revenue/PAT where official reconciliation exists.
2. **Reported-but-not-yet-cross-verified facts** — e.g. CFO when only the Screener statement is available.
3. **Derived metrics** — e.g. FCF, whose inputs and methodology must be explicit.

This is a more precise implementation target than creating a generic canonical table and labeling every number "canonical."

## 17. Next implementation slice

Use one representative company and four metrics:

1. Revenue
2. PAT
3. CFO
4. FCF

Trace each metric according to its actual evidence class:

```text
Revenue / PAT:
Screener + official filing
        ↓
existing verification record
        ↓
verified fact
        ↓
financial analytics

CFO:
Screener cash-flow statement
        ↓
reported-but-unverified fact
        ↓
financial analytics

FCF:
CFO + capex inputs
        ↓
deterministic Stocker calculation
        ↓
derived metric
```

The slice must preserve current outputs while proving:

- source provenance
- canonical metric
- period
- scope
- unit
- verification status
- calculation inputs
- calculation version

Only after this passes should the same pattern be generalized across the rest of the financial model.

## Bottom line

Stocker does **not** need a greenfield canonical-data rewrite.

It needs to **finish connecting the canonical architecture that already exists**.

That is the reform path.
