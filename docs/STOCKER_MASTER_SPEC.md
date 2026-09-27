# Stocker Master Specification

**Status:** Product and engineering source of truth  
**Current baseline:** v4.5, commit 9e956a7  
**Audience:** Stocker maintainers, Antigravity, coding agents, reviewers  
**Last updated:** 2026-09-27

## 1. Product purpose

Stocker is an AI-assisted fundamental investment research and opportunity-discovery system.

It is not merely a screener, dashboard, or black-box stock picker.

It should help the user answer:
1. Which companies deserve my attention now?
2. Once I choose a company, what is the complete evidence-based investment picture?

Important reasoning must be inspectable: the user should be able to move from a conclusion to underlying facts, sources, calculations, assumptions and uncertainty.

The product should feel simple to use while being highly disciplined underneath.

## 2. Two primary experiences

### Opportunity Discovery

Stocker searches a defined universe and identifies companies that deserve further investigation.

For each surfaced company, expose:
- business quality;
- financial quality;
- growth and growth durability;
- cash generation;
- balance-sheet/financial risk;
- management execution;
- valuation;
- key risks;
- evidence quality;
- major concern;
- what could invalidate the thesis;
- what deserves deeper research.

Deterministic ranking may be used internally, but the user-facing experience must not imply unjustified precision.

### Deep Company Research

A user can research any company, whether or not it appears in Opportunity Discovery.

The research picture should combine, where available:
- structured financial data;
- annual reports;
- earnings/concall/town-hall material;
- company/BSE/NSE announcements;
- relevant company documents;
- other permitted research sources.

It should cover:
- business model;
- segments/geography;
- industry;
- competitive position;
- historical financials;
- growth;
- profitability;
- cash generation;
- balance sheet;
- capital allocation;
- management statements versus execution;
- future growth drivers;
- risks;
- valuation;
- scenarios/sensitivities;
- Why NOT?;
- What would change our view?

## 3. Investment methodology

The intended pipeline is:

SOURCE → EVIDENCE → VERIFIED/CANONICAL FACTS → DETERMINISTIC ANALYSIS → BUSINESS/MANAGEMENT ANALYSIS → SECTOR-SPECIFIC ANALYSIS → VALUATION → SCENARIOS → INVESTMENT THESIS → OPPORTUNITY DISCOVERY / RESEARCH UI

Research should normally answer:
1. What is the business?
2. What industry/business model is it in?
3. What happened historically?
4. How good are its economics?
5. Is growth real and durable?
6. Does accounting profit convert into cash?
7. Is the balance sheet appropriate?
8. What has management said and delivered?
9. What can drive future growth?
10. What can go wrong?
11. What expectations are already reflected in the price?
12. What valuation does the evidence support?
13. How sensitive is the conclusion?
14. What would change the conclusion?

A good company is not automatically a good investment at any price.

## 4. Truth categories

Every important output must have a clear category:
- Reported fact: directly reported by a source.
- Verified fact: reported fact with sufficient verification/cross-checking.
- Stocker calculation: deterministic calculation from underlying facts.
- Management guidance: management's own forward-looking statement.
- AI interpretation: AI-derived interpretation of evidence.
- Stocker assumption/projection: Stocker's explicit forward-looking model assumption/output.

AI interpretation must never silently become a reported fact.

Derived metrics must never be presented as reported facts.

Missing values must remain missing unless an explicit methodology supports a derivation. Never silently turn missing data into zero.

## 5. Provenance and discrepancies

Important financial facts must be traceable to:
- metric;
- period;
- scope;
- unit/currency;
- source;
- source date;
- verification status;
- discrepancy status;
- downstream calculation.

Important conclusions must be traceable to:
- supporting facts;
- calculations;
- source evidence;
- AI interpretation where used;
- assumptions;
- uncertainty.

If sources disagree, show the discrepancy rather than silently choosing a value.

If evidence is insufficient, say so.

## 6. Existing architecture

Current v4.5 already contains substantial canonical/provenance infrastructure, including:
- company_registry: canonical company identity;
- source_documents: source/document registry;
- document/page caches;
- company_knowledge_facts: persistent qualitative evidence;
- financial_verification_records: financial verification;
- AI analysis/evidence persistence;
- financial truth/resolver infrastructure;
- taxonomy/company classification;
- deterministic financial analytics.

These are existing assets.

Do not create a new financial-facts architecture or rewrite the backend simply for architectural purity.

The goal is to connect, normalize, harden and complete what already exists.

Raw/source snapshots can exist for ingestion/recovery, but analytical logic should consume the appropriate canonical/verified representation wherever one exists.

## 7. Financial analysis

Deterministic code should handle, where meaningful:
- revenue/profit growth;
- margins;
- ROE/ROCE;
- capital efficiency;
- CFO;
- CFO/PAT;
- FCF;
- capex;
- working capital;
- leverage;
- interest coverage;
- liquidity;
- balance-sheet quality;
- dilution/share count;
- capital allocation;
- historical consistency.

All calculations must respect period, scope, unit and currency.

AI should not perform deterministic financial arithmetic.

## 8. Sector and business-model analysis

Stocker must not use one generic model for every company.

Architecture:

COMMON FINANCIAL TRUTH → BUSINESS/SECTOR CLASSIFICATION → SECTOR-SPECIFIC ANALYTICS → SECTOR-SPECIFIC VALUATION/FORECASTING → INTEGRATED THESIS

Examples:
- Banks/NBFCs: asset quality, credit growth, NIM where relevant, provisioning, capital adequacy, ROA/ROE, funding/liability structure, credit costs and other appropriate banking metrics. Do not treat bank debt like industrial debt.
- Insurers: appropriate underwriting/insurance economics and investment-income distinctions.
- Manufacturing/industrial: volumes/capacity, utilization, pricing, margins, capex, working capital, leverage, return on capital.
- Consumer: volume/value growth, pricing, margins, distribution, competitive position, capital efficiency, cash conversion.
- Software/IT: organic growth, margins, utilization, attrition, bookings/deal pipeline where available, cash generation, client concentration, capital-light economics.

The taxonomy must remain extensible.

## 9. Management analysis

Management commentary is evidence, not automatically truth.

Where meaningful, track:
- guidance;
- targets;
- capacity plans;
- margin goals;
- expansion plans;
- strategic commitments;
- capital-allocation statements.

Compare measurable promises with later observable outcomes.

Keep separate:
- stated target;
- target period;
- actual outcome;
- evidence quality;
- comparability.

Do not manufacture management scores using arbitrary achievement thresholds.

AI may extract and connect management evidence. Deterministic rules should evaluate measurable target-versus-actual relationships where semantics are sufficiently clear.

## 10. AI principles

AI is valuable for:
- reading long documents;
- extracting evidence;
- locating relevant passages;
- summarising management commentary;
- identifying qualitative risks;
- connecting statements;
- detecting contradictions;
- classifying evidence;
- explaining complex material simply.

AI should not be responsible for:
- basic arithmetic;
- CAGR/margins/valuation mathematics;
- silently filling missing financial values;
- inventing financial facts;
- overriding verified canonical data;
- unsupported numerical forecasts.

AI-derived evidence should preserve document, date/period, page/section where available, extraction timestamp and model/provider/version where relevant.

Document processing must handle malformed, incomplete, duplicate and stale sources safely.

## 11. Valuation

Valuation is an estimate, not a fact.

Separate:

OBSERVED INPUTS → DETERMINISTIC CALCULATION → ASSUMPTIONS → SCENARIO OUTPUT

Use methods appropriate to the business, potentially including DCF and earnings/multiple/cash-flow approaches.

Do not force one method on every company.

Terminal growth, discount rates, exit multiples and other assumptions must be explicit.

Use sensitivity analysis where conclusions are materially assumption-sensitive.

## 12. Investment thesis

Stocker's synthesis should answer:
- What is happening?
- Why might it continue?
- What is the market already assuming?
- What could go wrong?
- Why might the thesis be wrong?
- What would change our view?

The Why NOT discipline is mandatory.

## 13. Analyst View and Stocker View

Analyst View exposes evidence, calculations, assumptions, risks and scenarios without hiding uncertainty behind a conclusion.

Stocker View gives a concise evidence-backed synthesis explaining what Stocker sees, why, supporting evidence, key concerns, valuation context, uncertainty and what would change the view.

The Stocker View must be traceable to the underlying analysis.

## 14. Opportunity Discovery principles

Opportunity Discovery is a research-prioritization system, not a disguised guaranteed-buy list.

Internal deterministic ranking is acceptable, but user-facing results should expose:
- quality;
- growth;
- durability;
- cash;
- management;
- financial risk;
- valuation;
- downside;
- evidence quality;
- uncertainty.

Incomplete evidence must not make a company appear strong merely because missing values are treated as neutral or zero.

## 15. UX principles

The interface should be simple despite the complexity underneath.

Important concepts such as DCF, WACC, FCF, ROCE and valuation multiples should have beginner-friendly explanations.

For important numbers, users should be able to discover:

WHAT IS IT? → HOW WAS IT CALCULATED? → WHAT ARE THE INPUTS? → WHERE DID THEY COME FROM?

Existing provenance/formula-transparency UI should be preserved and expanded.

Avoid excessive dashboards, decorative scores and information overload.

## 16. Reliability, security and performance

Stocker is intended to be a long-lived production product.

Requirements include:
- durable persistence;
- safe startup/recovery;
- graceful provider/API failures;
- no silent corruption;
- no silent stale-data presentation;
- input validation;
- strong typing/schemas;
- indexed database access;
- pagination/lazy loading;
- background processing for expensive AI/document work;
- incremental ingestion;
- appropriate caching;
- observability;
- secure secrets;
- least privilege;
- safe document handling;
- prompt-injection protection;
- dependency/security hygiene;
- deterministic financial tests;
- integration/API tests;
- regression/golden tests;
- performance testing at universe scale.

Do not recompute expensive analysis for the entire universe on every ordinary request.

## 17. Historical time-travel / backtesting

Future capability:

Pretend today is date X.

Only information actually available by X may be used.

Store the analysis, evidence, valuation, thesis and risks as they existed at X, then compare with later actual outcomes.

Guard explicitly against:
- look-ahead bias;
- survivorship bias;
- data leakage;
- overfitting;
- data-mining.

This comes after the core investment engine is reliable.

## 18. Target architecture

SOURCE PROVIDERS
→ RAW/SOURCE RECORDS
→ CANONICAL SOURCE IDENTITY
→ VERIFIED/CANONICAL FACTS
→ DETERMINISTIC FINANCIAL ENGINE
→ BUSINESS + MANAGEMENT EVIDENCE
→ SECTOR-SPECIFIC ANALYSIS
→ VALUATION ENGINE
→ SCENARIOS/SENSITIVITY
→ INVESTMENT THESIS
→ OPPORTUNITY DISCOVERY
→ RESEARCH UI

Cross-cutting:
PROVENANCE | VERSIONING | FRESHNESS | VALIDATION | PERSISTENCE | OBSERVABILITY | CACHING | SECURITY | TESTING | BACKGROUND JOBS

This defines required behaviour and boundaries. It does not mandate a rewrite of working v4.5 internals.

## 19. What we must NOT do

Do not:
- rewrite the backend without evidence;
- replace working v4.5 truth/provenance infrastructure unnecessarily;
- add technical analysis before fundamentals are mature;
- add arbitrary ranking factors to improve-looking scores;
- tune thresholds merely to create attractive results;
- use AI where deterministic code is sufficient;
- create duplicate canonical financial stores without justification;
- add valuation knobs without methodology;
- build flashy UI before analytical correctness;
- claim confidence unsupported by evidence.

Ask:

Does this improve the underlying investment system, or merely make the demo look better?

Prefer a smaller number of reliable capabilities over a larger number of fragile ones.

## 20. Implementation roadmap

### Phase 1 — Current-system alignment
Compare current v4.5 against this specification. Classify major capabilities as:
- implemented correctly;
- partially implemented;
- architecturally weak;
- missing.

Do not rewrite working components.

### Phase 2 — Financial truth and analytical foundation
Harden important financial metric lineage, period/scope/unit handling and deterministic calculations.

### Phase 3 — Business, management and sector analysis
Strengthen sector-specific analysis and management evidence/execution.

### Phase 4 — Valuation and scenarios
Build transparent business-model-appropriate valuation and sensitivity.

### Phase 5 — Opportunity Discovery
Replace the legacy Top Bets / High-Conviction Decision Engine concept with transparent research prioritization.

### Phase 6 — Deep Research UX
Build the coherent company research experience, including Analyst View and Stocker View.

### Phase 7 — Scale, reliability and security
Harden the product for a growing universe and document corpus.

### Phase 8 — Historical time-travel/backtesting
Implement only after the preceding layers are trustworthy.

## 21. Preservation rule for v4.5

Current v4.5 already contains substantial work around:
- canonical financial truth;
- provenance;
- financial safety;
- common-period handling;
- sector/taxonomy routing;
- bank analytics;
- source deduplication;
- document intelligence;
- business analysis;
- deterministic guidance evaluation;
- AI evidence handling;
- self-explanatory financial UI;
- integration/e2e testing.

These are existing assets and must not be accidentally broken.

Any proposed replacement must first explain:
1. what is wrong;
2. why incremental correction is insufficient;
3. what regression tests will protect the change;
4. how existing truth/provenance guarantees remain intact.

## 22. Definition of done

Important functionality is complete only when it is:
- correct;
- persistent;
- traceable;
- testable;
- explainable;
- safe under missing/contradictory data;
- sector-aware where appropriate;
- performant at intended scale;
- consistent with this specification;
- understandable to a beginner.

Simple on the surface. Disciplined underneath.

We don't hide imperfections. We expose them.
