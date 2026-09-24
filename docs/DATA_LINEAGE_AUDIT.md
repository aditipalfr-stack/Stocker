# Phase 1 — Data Lineage Audit

## Purpose

Trace representative Stocker data from source ingestion through persistence, deterministic analysis, AI interpretation, API response, and UI presentation.

## Executive finding

The current system has the beginnings of a provenance-aware architecture, but the canonical lineage is not yet strong enough for a production-grade research system.

The largest issue is not that Stocker lacks sources. It is that one financial payload is copied through multiple representations and then consumed by analytics, projections, ranking, and UI without a formal immutable fact/evidence layer.

## Trace A — Revenue / Sales

### 1. Source

backend/scraper.py fetches Screener.in HTML using fetch_screener_html().

parse_screener_table() reads the profit-loss table and creates FinancialStatement periods plus FinancialRow(metric, values).

Source metadata retained at stock level includes source_name, source_url, statement_type, and fetched_at.

### 2. Persistence

fetch_stock_from_screener() serializes the entire stock payload and writes it to:
- backend/data/stocks_cache.json
- SQLite stocks_cache.data_json

This creates two persistent copies of the same underlying financial payload.

SQLite stores the full payload as one JSON blob keyed by symbol. It does not independently model source document, source version/hash, metric, period, scope, unit, extraction timestamp, or verification status.

### 3. Hydration

hydrate_stock_data() reconstructs the JSON blob into Pydantic models.

This is a type restoration step, not a provenance step.

### 4. Deterministic calculation

compute_financial_analytics() calls get_row_values(pl, Sales) or get_row_values(pl, Revenue).

It then derives 3Y/5Y/10Y CAGR, quarterly growth, and historical parameters.

The calculations themselves are deterministic and reusable.

Important weakness: get_row_values() uses fuzzy substring matching after exact matching. That is convenient but can create ambiguous metric selection if source schemas evolve.

### 5. Projection dependency

The projection layer consumes analytics and raw statements.

Current projection logic can use historical CAGR as a forward growth assumption and also contains fallback/default assumptions.

Therefore the chain from reported revenue to projection is not yet a clean separation between reported fact and analyst assumption.

The system must eventually preserve:

reported revenue -> deterministic historical calculation -> explicit assumption -> projection

with each transition visible.

### 6. Ranking dependency

Ranking consumes analytics and projection outputs.

The ranking result is therefore a derived conclusion, not a financial fact.

## Trace B — CFO / FCF

CFO is extracted from the raw Cash Flow statement.

The system explicitly filters several non-raw Screener-derived cash-flow metrics during parsing/hydration. This is a good safeguard.

compute_financial_analytics():
1. takes reported CFO;
2. looks for directly reported capex;
3. otherwise derives capex from fixed-asset delta + depreciation + CWIP delta;
4. calculates FCF = CFO - capex;
5. attaches confidence and anomaly warnings.

This is one of the strongest parts of the current financial engine because the calculation is deterministic and the methodology is partially exposed.

However, the resulting FCF is still stored inside broad analytics JSON rather than as a versioned analytical fact with explicit input references.

## Trace C — Qualitative management evidence

The document pipeline is:

source document -> document discovery -> PDF/page cache -> AI extraction -> structured qualitative evidence -> AI synthesis -> Stocker View

The database already contains:
- source_documents
- document_pages_cache
- ai_document_summaries
- ai_analysis_cache
- company_knowledge_facts

company_knowledge_facts is particularly important because it already models:
- symbol
- document URL/title/type
- period
- category
- metric
- raw stated value
- numeric value/unit
- target period
- claim type
- source quote
- source page
- extraction timestamp
- fact JSON

This should become a core part of the future evidence layer rather than remaining an auxiliary feature.

## API / UI lineage

backend/main.py calls build_full_stock_detail().

That function:
1. hydrates source data;
2. runs deterministic financial analytics;
3. obtains document intelligence;
4. runs projections;
5. runs ranking;
6. returns one large StockDetail.

GET /api/stocks loops through the active universe and performs this full computation for each company.

The frontend therefore receives final analytical objects rather than a formal lineage graph.

Existing DataOriginBadge and FormulaTransparencyModal components are useful foundations, but the backend does not yet expose a universal provenance object that those components can reliably consume.

## Findings

### P0 — No canonical financial fact layer

Raw financial statements remain embedded in stock JSON.

There is no normalized canonical fact model such as:

company + statement + metric + period + scope + unit + value + source + source_version + verification_status

This makes reconciliation, deduplication, historical snapshots, and source precedence harder than necessary.

### P0 — Duplicate persistence

The same stock payload is persisted in both JSON file cache and SQLite JSON blob.

The database also bootstraps identities from the legacy JSON cache.

The system therefore has two physical stores that can influence the effective source of truth.

### P0 — Freshness is not lineage

The 12-hour cache TTL tells us when the payload was fetched, but not which source version was used, whether the source subsequently changed, whether the value was verified, or whether derived analysis was calculated against the same source snapshot.

Freshness and provenance must become separate concepts.

### P0 — Facts and assumptions are mixed downstream

Historical values can become projection assumptions through heuristics/defaults.

Every important number should eventually be classified as one of:
- reported_fact
- derived_calculation
- management_guidance
- analyst_assumption
- projection
- scenario_assumption
- ai_interpretation

### P1 — Metric names are source-dependent

Fuzzy matching of metric names is pragmatic but insufficient as the canonical financial layer.

Stocker needs a controlled metric taxonomy and source-to-canonical mapping.

### P1 — Scope is not consistently attached to raw financial rows

Consolidated vs standalone is retained at stock payload level, but the fact itself should carry scope.

This matters when reconciling multiple sources.

### P1 — API performs expensive derivation on request

The API constructs analytics/projections/ranking while serving requests.

This makes response time, failure recovery, reproducibility, and historical snapshots harder.

## What we should preserve

1. Deterministic financial_engine.py calculations.
2. Explicit FCF methodology and confidence warnings.
3. Official-source verification work.
4. company_knowledge_facts provenance structure.
5. Source-document and PDF-page caching.
6. UI provenance concepts such as Data Origin and Formula Transparency.

## Target lineage

SOURCE DOCUMENT / FEED
        |
        v
RAW SOURCE RECORD (immutable)
        |
        v
CANONICAL VERIFIED FACT
        |
        +----> DETERMINISTIC CALCULATION
        |              |
        |              v
        |        ANALYTICAL FACT
        |
        +----> AI / QUALITATIVE EVIDENCE
                       |
                       v
                 EVIDENCE RECORD
                       |
                       v
              BUSINESS / SECTOR ANALYSIS
                       |
                       v
                  VALUATION
                       |
                       v
                INVESTMENT THESIS

Every derived number should be able to point backward to its inputs.

Every qualitative conclusion should point backward to its evidence.

## Recommended next implementation boundary

Do not rewrite the entire ingestion system yet.

First define schemas and lineage contracts for:
1. financial fact
2. derived calculation
3. qualitative evidence
4. source record
5. analytical snapshot

Then migrate one vertical slice — Revenue, PAT, CFO and FCF for one company — through that architecture and test it end-to-end.

Only after that should the old JSON-cache path be retired.

## Phase 1 conclusion

The current Stocker pipeline is payload-centric rather than evidence-centric.

That is the central architectural finding of this phase.

The correct next step is not to add more scoring or valuation logic. It is to establish a canonical, traceable evidence/fact layer and migrate one complete financial lineage through it without breaking the existing application.
