# Four-Metric Lineage Audit

## Purpose

This audit validates the **real persisted Stocker data path** for four representative metrics:

1. Revenue
2. PAT (Profit After Tax)
3. CFO (Cash Flow from Operating Activities)
4. FCF (Free Cash Flow)

The goal is not to prove that the class definitions look sensible. The goal is to trace actual persisted data through the existing database, canonical metric metadata, verification records, and deterministic financial calculations.

## Expected architecture

| Metric | What Stocker should store | Verification role | Calculation role |
|---|---|---|---|
| Revenue | Reported financial fact | Can be cross-verified against official filing | Input to analytics |
| PAT | Reported financial fact | Can be cross-verified against official filing | Input to analytics |
| CFO | Reported financial fact | Currently not part of the official Phase-B verified metric set | Input to FCF / cash-quality analytics |
| FCF | **Not a reported fact** | Must not be stored as an official verification fact | \`FCF = CFO - Capex\` |

The distinction is deliberate:

- **Canonical metric** answers: “What financial concept is this?”
- **Evidence status** answers: “What kind of evidence do we have?”
- **Verification record** answers: “Did the official-vs-Screener verification process establish agreement?”
- **Derived metric** answers: “Did Stocker calculate this from other facts?”

## Test implementation

\`backend/test_four_metric_lineage.py\` is a read-only integration audit.

It:

1. Opens the persisted \`backend/data/stocker.db\` in SQLite read-only mode.
2. Selects a representative non-bank company from the persisted \`stocks_cache\`.
3. Hydrates its persisted P&L, balance sheet and cash-flow statements.
4. Traces Revenue, PAT and CFO through the persisted \`FinancialRow\` metadata.
5. Looks up matching \`financial_verification_records\`.
6. Runs the existing deterministic \`compute_financial_analytics()\` path.
7. Traces FCF to its actual CFO and Capex inputs.
8. Fails if FCF has been incorrectly represented as an official verification record.
9. Prints a JSON lineage report so gaps are visible instead of hidden.

## What counts as success

### Revenue / PAT

A fully connected path should look like:

\`\`\`
stocks_cache.data_json
    ↓
FinancialRow
    ↓
canonical_metric = REVENUE / PAT
    ↓
source label + provider + period + unit + currency
    ↓
financial_verification_records (when official verification exists)
    ↓
financial analytics
\`\`\`

### CFO

The current intended path is:

\`\`\`
stocks_cache.data_json
    ↓
FinancialRow
    ↓
canonical_metric = CFO
    ↓
reported_unverified
    ↓
financial analytics
\`\`\`

CFO should not be labelled “verified” merely because the row is canonicalized.

### FCF

The intended path is:

\`\`\`
CFO row
   +
Capex input
   ↓
compute_financial_analytics()
   ↓
FCF = CFO - Capex
   ↓
stocker_derived_fcf_cr
\`\`\`

FCF should remain visibly derived. It should not become another “reported financial fact” simply because it is stored inside an analytics JSON object.

## Important audit interpretation

The test intentionally distinguishes **legacy metadata gaps** from actual financial-data errors.

Older persisted \`stocks_cache\` payloads may predate the new \`FinancialRow.canonical_metric\` fields. In that case the test can still resolve the metric through the controlled alias registry, but reports:

\`LEGACY_METADATA_GAP\`

That is useful evidence. It means the new canonical boundary exists in code but has not yet been propagated through every already-persisted payload.

The correct response is **not** to create another financial-facts table. The next engineering step, if the audit exposes this gap, is to define a safe migration/refresh strategy for persisted \`stocks_cache\` records and then re-run this audit.

## What this audit deliberately does not change

- No new financial-facts table
- No ranking changes
- No projection changes
- No DCF changes
- No AI prompt changes
- No source-precedence changes
- No automatic backfilling of financial values
- No mutation of the persisted database

This is an architecture-validation step, not a redesign.

## Run

From \`backend/\`:

\`\`\`bash
python -m pytest test_four_metric_lineage.py -s
\`\`\`

The \`-s\` flag is intentional: the test prints the actual lineage report.

If the persisted database is unavailable, the test fails explicitly rather than silently falling back to a synthetic fixture.
