# STOCKER ENGINEERING & PRODUCT CONTRACT
**Version**: 1.1 (Phase V4.1 Checkpoint)  
**Target Audience**: Developers, AI Coding Agents (Gemini, Codex), System Architects  
**Purpose**: Permanent product & architectural invariants for the Stocker codebase to prevent architectural drift, maintain verification integrity, and enforce fail-closed engineering.

---

## 1. Product Vision

Stocker is an evidence-based fundamental analysis and stock-selection application for Indian equities (NSE & BSE).

Its objective is to take any listed company through a strict, deterministic research pipeline:
$$\text{Company Identity} \longrightarrow \text{Financial Ingestion} \longrightarrow \text{Deterministic Analysis} \longrightarrow \text{Authoritative Verification} \longrightarrow \text{Source Filing Discovery} \longrightarrow \text{Document / Business Intelligence} \longrightarrow \text{Forward Projection} \longrightarrow \text{Ranking / Investment View}$$

### Core Distinctions
Stocker must always strictly distinguish and communicate to the investor:
1. **What was reported**: Raw stated numbers and text from company disclosures.
2. **What was officially verified**: Figures deterministically reconciled against official exchange XBRL/PDF filings.
3. **What Stocker calculated**: Mathematical formulas evaluated by deterministic code (CAGRs, CFO/PAT, margins, variances).
4. **What management said**: Corporate guidance, targets, and strategic statements.
5. **What Stocker projected**: DCF valuations and forward earnings trajectories based on explicit assumptions.
6. **What AI interpreted**: Qualitative synthesis, business model summaries, and moat analyses.
7. **What is unavailable or uncertain**: Explicit gaps in reporting or unresolved ambiguities.

> **Principle**: Accuracy, provenance, reproducibility, and investor usefulness are strictly more important than producing an answer at any cost.

---

## 2. Core AI Rule

$$\text{Permanent Principle: } \mathbf{AI\ extracts\ meaning} \longrightarrow \mathbf{Code\ verifies} \longrightarrow \mathbf{AI\ explains\ the\ verified\ result}$$

### Appropriate Use of AI
AI (Large Language Models) should be used solely for qualitative interpretation and document semantic extraction:
- Reading and understanding long official filings (Annual Reports, concall transcripts, investor presentations, announcements).
- Extracting stated management guidance, forward targets, and strategic priorities.
- Summarizing business models and monetization architecture.
- Identifying qualitative operational risks, headwinds, and competitive threats.
- Classifying economic moat categories and competitive advantages.
- Identifying specific facts and KPI claims worth structuring with page/quote citations.
- Synthesizing verified multi-document findings into an institutional executive view.

### Mandatory Role of Deterministic Code
Deterministic code must execute all math, logic, matching, and chronology:
- Company and security identity resolution.
- Period, fiscal year, and date alignment.
- Metric canonicalization and matching where rules are deterministic.
- Mathematical computations: QoQ, YoY, CAGRs, median margins, CFO/PAT ratios, FCF, Net Debt, CWIP %, working capital debtor/inventory cycles.
- Promise vs outcome evaluation: matching stated promise deadlines against subsequent reported periods, calculating milestone achievement percentages, and assigning deterministic status badges (`Delivered`, `In Progress`, `Delayed`, `Missed`, `Not Enough Evidence`).
- Management guidance vs DCF projection triangulation (calculating exact variance in basis points).
- Currency scale normalization (Crores, Millions, Billions, per share).
- DCF arithmetic, scenario modeling, terminal values, and intrinsic valuation math.
- Ranking engine evaluation and sorting rules.
- Confidence score aggregation.

> **Rule**: Never ask AI to calculate something code can calculate reliably.

---

## 3. Fail-Closed Principle

> **Rule**: Unknown must remain unknown. Never invent data or upgrade ambiguous figures into certainty.

### Prohibited Conversions
- Never turn `missing` $\to$ `0.0`.
- Never turn `Unknown Currency` $\to$ `INR`.
- Never turn `Unknown Reporting Scope` $\to$ `Consolidated`.
- Never turn `Unknown Unit` $\to$ `₹ Cr` or `₹ / Share`.
- Never assign an ambiguous date/period to the nearest available period without proof.
- Never map an ambiguous input to a guessed ticker without evidence.
- Never invent missing financial projection assumptions (e.g., fallback 10% defaults) and label them as company guidance.

### Explicit Verification States
Financial verification and claim matching must output explicit deterministic statuses:
- `VERIFIED`: Exact mathematical match within defined tolerance under proven scope, unit, and period.
- `DISCREPANCY`: Verified source figure exists but diverges materially from stated data.
- `NOT_COMPARABLE`: Scope, period duration, or accounting standard differs.
- `INSUFFICIENT_EVIDENCE`: Official filing does not contain verifiable breakdown or facts.
- `OFFICIAL_SOURCE_MISSING`: Official filing not discoverable or unreadable.
- `SCREENER_VALUE_MISSING`: Reference statement lacks corresponding metric row.

Unsafe, unverified, or ambiguous evidence must never silently influence high-confidence investor conclusions.

---

## 4. Research Lifecycle

Every company in Stocker progresses through explicit, trackable research stages:

| Lifecycle Stage | Valid States | Description |
| :--- | :--- | :--- |
| **1. Identity** | `unresolved`, `resolved`, `officially_verified` | Security resolution from raw user input to canonical BSE/NSE/ISIN identity. |
| **2. Financial Data** | `missing`, `ready`, `stale`, `error` | Ingestion and local caching of standardized reported financial statements. |
| **3. Deterministic Analysis** | `not_ready`, `ready` | Calculation of statement ratios, margins, CAGRs, working capital, and diagnostics. |
| **4. Official Verification** | `not_run`, `partial`, `verified`, `discrepancy` | Multi-source reconciliation of latest reported figures against official exchange XBRL/PDF filings. |
| **5. Source Filings** | `not_searched`, `partial`, `ready`, `error` | Discovery and indexing of Annual Reports, Concalls, Presentations, and Announcements. |
| **6. Business Analysis** | `not_run`, `running`, `ready`, `stale`, `error` | AI extraction of qualitative business drivers, moat, promise-tracking, and executive synthesis. |
| **7. Projection** | `unavailable`, `historical_only`, `evidence_enriched`, `stale` | DCF forward valuation models and scenario projections. |
| **8. Investment Score** | `unavailable`, `provisional`, `evidence_enriched`, `incomplete` | Fundamental ranking and conviction score. |

The application API and UI must represent and expose these states explicitly.

---

## 5. Add-Company Workflow

User input may vary widely:
- Ticker symbol (e.g., `COLPAL`, `TCS`, `INFY`)
- Exchange-specific security code (e.g., `500830`)
- Partial company name (e.g., `Colgate`, `HDFC`)
- Full legal company name (e.g., `Colgate-Palmolive (India) Ltd`)
- Known corporate alias or brand

### Correct Ingestion Flow
$$\text{User Input} \longrightarrow \text{Canonical Security Resolver} \longrightarrow \text{Financial Ingestion} \longrightarrow \text{Local Persistence} \longrightarrow \text{Deterministic Calculations} \longrightarrow \text{Usable Stock Detail}$$

- **Mandate**: Frontend must never treat arbitrary raw user input as a final ticker and send it directly to a scraper or downstream pipeline.
- Input must pass through the authoritative company registry and resolver first.
- Inputs like `COLPAL`, `Colgate`, and `Colgate Palmolive India` must resolve to the identical canonical entity (`COLPAL` / `500830` / `INE181A01017`).

---

## 6. What Must Be Available Without AI

Following successful financial statement ingestion, all deterministic analytics must be immediately available without requiring an LLM or API key:
- Raw Quarterly financial statements.
- Annual Profit & Loss statements.
- Balance Sheets.
- Cash Flow statements.
- QoQ and YoY growth rates.
- 3-year, 5-year, and 10-year Sales and PAT CAGRs.
- Historical operating and net profit margins.
- CFO to PAT conversion ratios.
- Capex and Free Cash Flow (FCF) calculations.
- Net Debt, Debt-to-Equity, and Interest Coverage ratios.
- Working Capital cycles (Debtor Days, Inventory Days, Cash Conversion Cycle).
- Return ratios (ROCE, ROE, ROIC).
- Historical metric trend charts.
- Deterministic financial red flag diagnostics.

AI is strictly optional and additive; core financial analysis must operate entirely offline/deterministically.

---

## 7. Document Workflow

$$\mathbf{Document\ Discovery} \neq \mathbf{Document\ Analysis}$$

### Document Discovery (Lightweight & Non-Blocking)
- Discovers Annual Reports, concall transcripts, investor presentations, and corporate announcements from official sources.
- Indexes metadata: filing title, document type, publication period/date, direct URL, source host, validation status.
- Persists records into `source_documents` table.
- **Rule**: Document discovery must never block or delay initial financial statement ingestion.

### Document Analysis (On-Demand & Intensive)
- Triggered explicitly by the user ("Run Live AI Analysis").
- Reads document content and extracts structured claims, guidance targets, and recent corporate developments.
- Persists structured facts with verified source page and quotation citations.
- Runs deterministic code to audit claims against standardized reported financial results across multi-period series.

---

## 8. Business Analysis Architecture

The investor-facing Business Analysis UI is strictly organized into **4 structured views**:

1. **Investment View**:
   - Executive fundamental thesis & management execution verdict badge.
   - What changed recently (structural, capex, pricing shifts with citations).
   - Key positive growth triggers and catalyst milestones.
   - Critical operational and industry risks.
   - What to watch over the next 2–4 quarters.
2. **Business & Growth**:
   - Business model and monetization architecture.
   - Segment revenue mix & geographical reach.
   - Demand momentum, volume indicators, and order pipeline.
   - Multi-filing operational KPI time-series evolution.
   - Capacity expansion roadmaps and capex pipeline.
   - Competitive position, economic moat durability, and pricing power.
3. **Management & Execution**:
   - Promise vs Delivery track record (audited commitments vs reported outcomes with dual citations).
   - Management Guidance vs Stocker DCF Projections triangulation (basis-point variance analysis).
   - Capital allocation audit (CWIP efficiency, reinvestment rate, shareholder dividend discipline).
   - Governance and accounting watch (working capital drift, auditor observations, legal contingencies).
4. **Source Filings**:
   - Unified searchable directory of official Annual Reports, Concalls, Presentations, and Announcements.
   - Per-document AI key takeaways and management tone assessments.
   - Extracted structured facts with verified page numbers and source quotes.

---

## 9. Projections & Assumptions

### Projection Classification
- **Historical-Only / Preliminary**: Generated before Business Analysis is run. Must be constructed strictly using actual historical company financials, deterministic historical trends/medians, explicit evidence-derived assumptions, or explicit user overrides. If a material assumption cannot be supported by historical evidence, it must remain unavailable or low-confidence rather than being silently replaced by generic company-looking defaults (e.g., 10% revenue growth, 18% OPM, 5% capex, 25% tax, 22x P/E). A projection may be explicitly `unavailable` if sufficient evidence does not exist. Clearly badged as `Historical-Only`.
- **Evidence-Enriched**: Generated after Business Analysis incorporates verified management targets, capacity commissioning schedules, and audited capex outlays.

### Assumption Provenance
Every critical projection assumption must explicitly state:
- `value`: Numeric percentage or multiplier (e.g., `14.5%`).
- `source`: Provenance tag (`Management Guidance`, `Historical Median`, `Stocker Derived`, `User Override`).
- `period`: Target timeframe (e.g., `FY26-FY28`).
- `derivation`: Explicit explanation of mathematical or document basis.
- `confidence`: `High`, `Moderate`, `Low`.

> **Dependency Invalidation**: If upstream evidence, financial statements, or document facts change, dependent projection and valuation outputs must be marked stale and recomputed.

---

## 10. Investment Score & Conviction

Investment score (valuation/quality attractiveness) and research evidence confidence are separate dimensions:
1. **Investment Score**: Valuation upside, business quality, capital efficiency, and earnings momentum.
2. **Evidence Confidence**: Depth of official verification, availability of primary filings, and audit track record.

> **Principle**: A stock with high theoretical upside but incomplete filing evidence must not be presented with the same conviction as a stock backed by deep, verified multi-year filings.

---

## 11. Claim-Type-Aware Financial Truth Hierarchy

Because different sources establish fundamentally different categories of facts, Stocker employs a **Claim-Type-Aware Truth Model** rather than a simplistic universal precedence order:

1. **For Reported Financial Statement Figures**:
   - Official exchange/company statutory filings (XBRL / PDF results) with proven `company` + `security` + `period` + `scope` + `metric` + `unit/currency` are **authoritative** over secondary standardized ingestion (e.g., Screener).
2. **For Management Guidance & Strategic Statements**:
   - The primary company filing, concall transcript, investor presentation, annual report, or exchange announcement where management actually made the statement is the **authoritative** source.
3. **For Stocker Calculations**:
   - The authoritative source is the underlying compatible reported facts plus the deterministic formula.
4. **For AI Interpretation**:
   - AI is **never** an authoritative factual source; it interprets and synthesizes cited primary evidence.

### Strict Comparability Preconditions
No source or figure may override or reconcile against another unless the facts are proven comparable across all dimensions:
- Same company and security identity
- Exact reporting period duration and ending date
- Exact reporting scope (Standalone vs Consolidated)
- Compatible canonical metric definition
- Known and normalized unit and currency
- Appropriate claim type

> **Rule**: Unknown, non-comparable, or ambiguous evidence fails closed.

---

## 12. Data Persistence & Git Cleanliness

Runtime and user research state must persist independently of source code control:
- **Never Git-Track Runtime Data**: `backend/data/stocker.db`, `backend/data/stocks_cache.json`, downloaded filings, PDF caches, `__pycache__`, and `frontend/dist` must never be committed to Git.
- **Persistence Integrity**: Performing a `git checkout`, `git pull`, or `git reset` must never delete user-added companies or cached research state.
- **Infrastructure Simplicity**: SQLite and local file caches are sufficient for current scale. Do not introduce Redis, Kafka, or external database infrastructure without explicit, demonstrated requirements.

---

## 13. Performance Constraints

- **Lightweight Primary Endpoints**: Primary views (`/business-analysis`, `/stocks/{symbol}`) must return compact payloads and avoid embedding heavy filing archives or large document arrays.
- **Lazy Loading**: Heavy filing lists and per-document summaries must load lazily via dedicated endpoints (`/source-filings`).
- **No Redundant Recomputations**: Avoid reconstructing `build_full_stock_detail()` or running full DCF projection math for unrelated lightweight requests.
- **Client-Side Cache Reuse**: Frontend parent views must cache fetched data across tab switches to eliminate duplicate network calls for the same symbol.
- **Incremental Sourcing**: Document discovery and filing verification must use date-window boundaries to fetch only newly published filings.

---

## 14. Provenance Labels

All data displayed to the user must carry one of the standard provenance labels:

| Label | Description |
| :--- | :--- |
| **Reported Fact** | Stated number or text from standardized reported financial statements or company disclosures. |
| **Officially Verified** | Deterministically reconciled against official exchange filings (NSE/BSE). |
| **Management Guidance** | Verbatim forward statement or target stated by company management. |
| **Stocker Calculation** | Deterministic mathematical calculation evaluated by Python engine. |
| **Stocker Projection** | Forward DCF scenario model or intrinsic value estimate. |
| **AI Interpretation** | Qualitative synthesis, moat analysis, or tone assessment by LLM. |

---

## 15. Parked / Future Items

The following complex challenges are explicitly tracked as future roadmap items rather than assumed to be solved:
1. **Difficult / Scanned Official PDFs**: Universal extraction from scanned or non-standard graphical PDF tables without XBRL.
2. **NIFTY-500 Scale Automation**: Background scheduling and rate-limited mass ingestion across 500+ tickers simultaneously.

---

## 16. Current Known Architecture Debt

The following architectural debt items are documented for systematic resolution in upcoming phases:
1. **Add-Stock Frontend Bypass**: Frontend quick-add currently bypasses the authoritative company registry resolver for some direct symbol inputs.
2. **Ticker / Name Resolution Edge Cases**: Non-standard aliases (e.g., `COLPAL` vs `Colgate-Palmolive (India) Ltd`) require unified resolver coverage.
3. **Git-Tracked Runtime DBs**: `stocker.db` and `stocks_cache.json` have historically been tracked in Git, risking overwrite during branch operations.
4. **Persistence of Added Companies**: Manually added companies in SQLite risk being reset if binary DB files are checked out from older commits.
5. **Empty-Universe Bootstrap**: Handling bootstrap initialization when starting with zero pre-seeded companies in local storage.
6. **Zero vs Unavailable Ratio Defaulting**: Certain missing financial ratios default to `0.0` rather than explicit `None` / `Unavailable`.
7. **Official Verification Pipeline Governance**: Official verification currently exists beside the decision pipeline rather than underneath it. It does not yet fully govern canonical financial facts $\to$ deterministic analytics $\to$ projections $\to$ ranking / investment conclusions.
8. **V4 Fundamental Models Document Extraction Wiring**: `BusinessQuality`, `CompetitivePosition`, `CapitalAllocationAudit`, and `GovernanceAndForensicWatch` models require automated LLM prompt extraction wiring.
9. **Hardcoded Fallback Mappings**: BSE / Company IR document discovery uses fallback dictionary mappings for specific legacy tickers.
10. **Document Date Normalization**: Filing discovery sorting requires deterministic multi-format date normalization across all exchange sources.
11. **Document Subset Selection**: Multi-document AI synthesis currently selects a prioritized subset of filings rather than dynamic multi-year indexing.
12. **Theme-Based Page Selection**: PDF page extraction keyword filters require expansion to include governance, forensic accounting, and moat keywords.
13. **Native PDF Parsing Limitations**: Text-based PDF extraction fails closed on image-only scanned disclosures.
14. **Prompt Context Source Labeling**: Financial tables in AI prompt contexts should be explicitly badged as Screener-standardized vs Exchange-verified.
15. **Projection Fallback Defaults**: DCF engine contains legacy fallback percentages when historical statement series are brief.
16. **Hardcoded Projection Years**: DCF projection tables assume fixed forward fiscal year spans rather than dynamic period generation.
17. **Banking / NBFC Model Specialization**: DCF and valuation metrics are optimized for industrial/services firms and need specialized banking models (NIM, NPA, CASA, P/B).
18. **Post-AI Dependency Staleness**: After Business / AI Analysis completes or is refreshed, dependent outputs such as evidence-enriched projections, DCF valuations, investment scores/rankings, and thesis takeaways may remain based on the previous historical/no-AI state until a manual reload or recomputation occurs. The system requires an explicit dependency invalidation and recomputation cascade when upstream evidence changes.
19. **UI Lifecycle State Communication**: The UI should explicitly show research lifecycle badges (Identity Verified, Statement Ingested, Filings Discovered, AI Analyzed).

---

## 17. Development Rules

Every future phase must adhere to these engineering rules:
1. **Dedicated Branching**: Work strictly on the designated feature branch created from the approved parent commit.
2. **Preserve Working Checkpoints**: Never break previously approved Phase A/B/V4 capabilities.
3. **No Committing Runtime Artifacts**: Keep `.db`, `.json` caches, logs, `__pycache__`, and `dist` strictly untracked.
4. **Comprehensive Executed Tests**: All changes must be verified with actually executed Python tests and frontend production builds.
5. **Commit Integrity**: Commit with clean, descriptive conventional commit messages and provide starting and final Git commit SHAs.
6. **No Unapproved Merging**: Never merge directly to `main` without explicit review.
