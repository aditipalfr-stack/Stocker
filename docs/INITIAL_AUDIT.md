# Stocker — Phase 0 Baseline Audit

**Audit date:** 2026-09-25  
**Repository:** `aditipalfr-stack/Stocker`  
**Branch:** `audit/phase-0-baseline`

## Purpose

This is the first baseline audit before major redevelopment of Stocker.

The objective is **not** to make the existing application look better or to patch individual symptoms. The objective is to establish what is currently trustworthy, what is reusable, what is structurally unsafe, and what must change to reach the agreed Stocker quality bar.

The target is a long-lived, evidence-first fundamental investment research system with high standards for correctness, persistence, performance, security, explainability, maintainability, and UX.

---

## 1. Current system at a glance

The repository currently contains:

- FastAPI/Python backend
- React 19 + TypeScript/Vite frontend
- SQLite persistence
- Screener.in financial-data ingestion
- NSE/BSE/official-filing verification infrastructure
- PDF/document sourcing and extraction
- AI document intelligence
- financial analytics
- projection/DCF engine
- multi-factor ranking engine
- comparison and detailed research UI
- tests and validation utilities

The current high-level execution path is approximately:

`source ingestion → cached financial data → financial analytics → document intelligence → projections/DCF → composite scoring → verdict/ranking → React UI`

This is a useful foundation, but it is **not yet the architecture we want to preserve as-is**.

---

# 2. What should be preserved

Several parts of the current implementation are valuable foundations.

### 2.1 Financial statement extraction

The application already works with reasonably granular:

- quarterly results
- annual P&L
- balance sheet
- cash flow
- ratios
- historical periods

This is much more useful than building the product around vendor-provided summary ratios alone.

### 2.2 Deterministic financial analytics

There is already a dedicated financial analytics layer for items such as:

- growth rates
- CAGR
- cash-flow quality
- FCF
- balance-sheet trends
- CWIP/capital-intensity indicators
- quarterly trends

The separation between reported financial inputs and derived analytics is directionally correct.

### 2.3 Official-source verification

`official_financial_service.py` contains unusually conservative verification logic, including:

- exact-period matching
- exact-scope matching
- explicit unit handling
- conservative metric mapping
- ambiguous EPS rejection
- fail-closed behaviour
- separate handling for financial institutions

This is aligned with Stocker's future evidence architecture and should be treated as a strong foundation rather than discarded.

### 2.4 Document intelligence

The document pipeline already attempts to preserve:

- document identity
- source URL
- page-level evidence
- extracted facts
- management guidance
- promise vs delivery
- growth drivers
- risks
- KPI evolution

This is valuable, but the AI output needs to become a clearly bounded evidence/interpretation layer rather than a hidden source of investment conclusions.

### 2.5 Transparency UI foundations

The frontend already contains:

- `DataOriginBadge`
- `FormulaTransparencyModal`
- financial statement views
- concept help/glossary
- source links

These are exactly the kinds of primitives the final product needs.

---

# 3. Critical findings

## P0 — Repository/data architecture is not yet production-grade

The repository currently contains persistent runtime data directly under `backend/data/`, including:

- `stocker.db` (~18 MB)
- PDF cache files
- stock cache JSON
- document-intelligence JSON

This creates several problems:

1. application state is coupled to Git
2. large binary/runtime artifacts are versioned as source
3. database state can diverge from code/schema
4. merges can become dangerous
5. repository size will grow with every data refresh
6. reproducibility and deployment semantics become unclear
7. persistent production data and application source are not cleanly separated

**Direction:** code/schema/migrations belong in Git; runtime financial/document data belongs in a proper persistence layer outside source control.

For the local/private phase SQLite may remain the right technology, but the storage architecture must be redesigned before scaling.

---

## P0 — Current analysis pipeline is too tightly coupled

`main.py` currently orchestrates:

`ingestion → analytics → document intelligence → projections → scoring → API response`

This makes the API layer responsible for too much domain logic and causes expensive work to be recomputed during requests.

For example, the stock-list endpoint loops through the entire universe and builds full stock details, including analytics, document intelligence and projections, before returning summaries.

That will not scale cleanly to a large universe.

**Direction:** introduce explicit application/domain services and persisted analysis artifacts. API requests should retrieve prepared results where possible rather than recomputing the world.

---

## P0 — Current investment verdict architecture conflicts with the new philosophy

The application still presents itself as:

> “Fundamental Stock Screener & Decision Engine”

and prominently uses:

> “High-Conviction Bets”

> “Score 0–100”

> “High Conviction Buy”

The current ranking engine combines growth, cash quality, capital efficiency, safety and valuation into a composite score and then maps the result into verdict labels.

This creates false precision and conflates several different questions:

- Is the business good?
- Is management executing?
- Is the balance sheet safe?
- Is growth durable?
- Is the valuation attractive?
- What is the downside?
- How strong is the evidence?

These should become separate analytical dimensions.

**Direction:** retain useful underlying calculations, but redesign the conclusion architecture around evidence, quality, valuation, uncertainty, scenarios and explicit reasons.

---

## P0 — Projection engine contains unjustified assumptions

Current projection logic includes defaults/heuristics such as:

- default growth rates
- default OPM
- default tax rate
- default P/E
- fixed 12% WACC
- fixed 5% terminal growth
- historical growth used directly as a forward assumption
- heuristic growth boosts
- heuristic margin adjustments
- heuristic bull/bear changes
- fallback revenue derived from market cap/P/E
- simplified cash-flow projection

These may produce plausible-looking numbers but do not meet the intended Stocker standard.

**Direction:** assumptions must become explicit, sourced, configurable, auditable and sensitivity-aware. Missing evidence should produce uncertainty/insufficient evidence rather than silent invented inputs.

---

## P0 — FCF projection methodology is too simplified

The projection engine currently derives CFO using a simplified relationship involving PAT and depreciation rather than building a proper working-capital/cash-flow model.

This can materially distort projected FCF.

**Direction:** distinguish:

- reported CFO
- normalized CFO
- working-capital effects
- capex
- maintenance/growth capex where supportable
- FCF
- projected FCF

Each must have a defined methodology and provenance.

---

## P0 — Sector models are not sufficiently differentiated

The current system identifies banking/financial companies using broad string checks and then applies simplified alternatives.

A bank, NBFC, insurer, manufacturer, software company and consumer business have fundamentally different economics.

**Direction:** establish a sector/model taxonomy and sector-specific analytical contracts before expanding ranking/valuation.

The system should know when a metric is:

- applicable
- not applicable
- differently defined
- insufficiently reliable

---

## P1 — Data model is partially normalized but still stores large JSON blobs

The database has useful tables for:

- stocks
- documents
- PDF pages
- AI summaries
- AI analysis
- knowledge facts
- company registry
- verification records

However, important financial data is still stored as large serialized JSON payloads.

This makes:

- querying
- deduplication
- provenance
- historical versioning
- incremental updates
- cross-company analytics

harder than necessary.

**Direction:** define canonical entities and facts first, then determine which data belongs relationally and which genuinely benefits from JSON.

Do not normalize blindly; normalize where it improves integrity and queryability.

---

## P1 — Multiple persistence mechanisms exist

The repository currently contains both:

- SQLite database persistence
- `stocks_cache.json`

The test suite explicitly verifies the JSON cache.

This creates two possible sources of truth.

**Direction:** establish one canonical persistence path. Caches must be derived/replaceable, never authoritative.

---

## P1 — AI and evidence boundaries need tightening

The system already has a useful `DataOriginBadge` concept with categories such as:

- reported fact
- Stocker calculation
- management guidance
- AI interpretation
- Stocker projection

This should become a formal domain contract.

AI must not silently transform:

> “management said X”

into:

> “X will happen”

or allow a qualitative extraction to become a numerical assumption without an explicit analytical step.

**Direction:**

`source → verified fact → calculation → interpretation → assumption → scenario → conclusion`

Every transition must be explicit.

---

## P1 — Security posture needs hardening

The current FastAPI configuration uses permissive CORS:

`allow_origins=["*"]`

combined with credentials enabled.

This is inappropriate for a hardened application.

The application also exposes runtime AI-key configuration through the UI. That workflow requires a deliberate secrets architecture before the product is considered secure.

**Direction:** secrets must never become ordinary application data, logs, client-side state, or Git history. CORS, authentication, authorization and secret handling will be redesigned as part of the platform architecture.

---

## P1 — Runtime computation is too expensive for the intended universe

The stock-list endpoint currently processes the universe synchronously and builds full analytical details for each company.

That is acceptable for a prototype with a small dataset but not for a continuously maintained large universe.

**Direction:** move toward:

- incremental ingestion
- persisted analytical snapshots
- background jobs
- cacheable derived artifacts
- targeted recalculation
- pagination
- indexed queries
- explicit freshness states

---

## P1 — Testing is useful but not yet a production safety net

There are tests for parsing, live ingestion, financial analytics and validation.

However, the current test suite also depends on live external sources.

There is not yet a sufficiently strong deterministic test architecture for:

- financial formulas
- historical reproducibility
- source precedence
- reconciliation
- valuation sensitivity
- sector-specific calculations
- persistence invariants
- API contracts
- security
- performance
- time-travel isolation

**Direction:** build a layered test strategy:

1. pure unit tests
2. deterministic financial fixtures
3. database/integration tests
4. provider contract tests
5. API tests
6. end-to-end tests
7. regression/golden datasets
8. historical time-travel tests
9. performance tests

Live-provider tests should be supplemental, not the primary correctness test.

---

# 4. Frontend findings

The frontend has a substantial amount of useful functionality, but its information architecture reflects the old “decision engine” philosophy.

Current concepts include:

- Leaderboard & Top Bets
- High-Conviction Bets
- composite score
- verdict badges
- score bands
- investment thesis

This should eventually evolve toward:

### Opportunity Discovery

> Companies worth investigating now

with transparent reasons for inclusion.

### Company Research

> Evidence → business quality → management → financials → risks → valuation → scenarios → Stocker View

### Analyst View

Evidence and calculations without hiding the reasoning behind a single score.

### Stocker View

A conclusion supported by the evidence, including:

- why
- why not
- valuation
- key assumptions
- uncertainty
- what would change the view

The current transparency components should be retained and expanded rather than replaced.

---

# 5. Architecture target

The eventual architecture should move toward:

`SOURCE PROVIDERS`
↓
`RAW / IMMUTABLE SOURCE RECORDS`
↓
`VERIFIED CANONICAL FACTS`
↓
`DETERMINISTIC FINANCIAL ENGINE`
↓
`QUALITATIVE / AI EVIDENCE ENGINE`
↓
`BUSINESS & MANAGEMENT ANALYSIS`
↓
`SECTOR-SPECIFIC UNDERWRITING`
↓
`VALUATION ENGINE`
↓
`SCENARIOS / SENSITIVITY`
↓
`INVESTMENT THESIS`
↓
`OPPORTUNITY DISCOVERY`
↓
`RESEARCH UI`

Cross-cutting systems:

- persistence
- provenance
- versioning
- validation
- observability
- caching
- security
- testing
- job orchestration

---

# 6. What we should NOT do yet

Do not immediately:

- rewrite the entire backend
- redesign every screen
- add technical analysis
- add more scoring factors
- add more AI prompts
- add more data providers simply because they are available
- tune the current score until it “looks right”
- add more DCF knobs
- migrate to microservices prematurely

First establish the foundation.

---

# 7. Recommended next audit phases

### Phase 0 — Baseline audit
**Status: in progress / established by this document**

Understand current code, data, runtime flow and risk areas.

### Phase 1 — Data lineage audit
Trace a single important number end-to-end:

`source → stored data → verification → calculation → API → UI`

Do this for several representative metrics.

### Phase 2 — Architecture audit
Map modules, dependencies, boundaries, coupling and expensive execution paths.

### Phase 3 — Persistence/database audit
Inspect every table, relationship, index, duplication path, cache and lifecycle.

### Phase 4 — Financial-methodology audit
Audit every calculation and assumption before replacing the projection/ranking layer.

### Phase 5 — AI/document audit
Determine exactly what is extracted, what is verified, what is inferred and what is generated.

### Phase 6 — Frontend/UX audit
Map the existing screens against the new product model and identify what should be retained, redesigned or removed.

### Phase 7 — Security/reliability/performance audit
Threat model the application, identify failure modes, measure expensive operations and define the engineering baseline.

---

# 8. Current overall assessment

The existing Stocker is **not a failed project**.

It has a meaningful amount of useful work already implemented, especially around financial data extraction, document sourcing, verification, financial analytics and transparency.

However, it is currently closer to a **feature-rich prototype/research tool** than the durable product we have now defined.

The most important decision is therefore:

> **Do not keep adding features on top of the current scoring/projection architecture.**

We should first establish the canonical data and evidence architecture, then rebuild the analytical/conclusion layer on top of it.

That approach protects the valuable work already done while preventing the current weaknesses from becoming permanent architectural debt.

---

## Audit status

**No production code has been changed by this audit.**

The next implementation decision should follow the Phase 1 data-lineage audit rather than starting with cosmetic UI work or a wholesale rewrite.
