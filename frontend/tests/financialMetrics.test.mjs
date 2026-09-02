import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  calculatePeriodChange,
  getMetricPresentation,
  selectStatementPeriods
} from '../src/utils/financialMetrics.ts';
import { getStatementGlossaryTerm } from '../src/data/statementGlossary.ts';
import {
  PROVENANCE_STATUS_PRESENTATION,
  STOCKER_STATUS_GUIDE
} from '../src/data/statusGuide.ts';
import { getFinancialConceptGuide, getRelevantSectorNotes, glossary, glossaryEntries } from '../src/data/glossary.ts';
import { buildCashFlowAnalysisTable } from '../src/utils/cashFlowAnalysis.ts';

test('A: revenue 100 to 110 is +10.0%', () => {
  const change = calculatePeriodChange('Revenue', 110, 100);
  assert.equal(change?.label, '+10.0%');
  assert.equal(change?.tone, 'positive');
});

test('B: revenue 100 to 90 is -10.0%', () => {
  const change = calculatePeriodChange('Revenue', 90, 100);
  assert.equal(change?.label, '-10.0%');
  assert.equal(change?.tone, 'negative');
});

test('C: OPM 18 to 20 is +200 bps, not percentage growth', () => {
  const change = calculatePeriodChange('OPM %', 20, 18);
  assert.equal(change?.label, '+200 bps');
  assert.equal(change?.unit, 'basis points');
});

test('D: GNPA 2.5 to 2.0 is -50 bps with positive tone', () => {
  const change = calculatePeriodChange('GNPA %', 2, 2.5);
  assert.equal(change?.label, '-50 bps');
  assert.equal(change?.tone, 'positive');
});

test('E: PAT negative to positive is a profitability transition', () => {
  const change = calculatePeriodChange('PAT', 50, -100);
  assert.equal(change?.label, 'Turned profitable');
  assert.equal(change?.percentChange, null);
  assert.equal(change?.tone, 'positive');
});

test('F: a positive flow turning negative is not shown as an unstable percentage', () => {
  const change = calculatePeriodChange('Net Profit', -50, 100);
  assert.equal(change?.label, 'Turned negative');
  assert.equal(change?.percentChange, null);
  assert.equal(change?.tone, 'negative');
});

test('G: zero to non-zero says From zero and zero to zero is Flat', () => {
  assert.equal(calculatePeriodChange('Revenue', 100, 0)?.label, 'From zero');
  assert.equal(calculatePeriodChange('Revenue', 0, 0)?.label, 'Flat');
});

test('H: quarterly selection uses the exact immediately preceding fiscal quarter', () => {
  const selection = selectStatementPeriods(['Dec 2025', 'Mar 2026', 'Jun 2026'], 'quarterly');
  assert.equal(selection.currentPeriod, 'Jun 2026');
  assert.equal(selection.previousPeriod, 'Mar 2026');
});

test('I: a missing prior quarter produces no comparison instead of using an adjacent period', () => {
  const selection = selectStatementPeriods(['Dec 2025', 'Jun 2026'], 'quarterly');
  assert.equal(selection.currentPeriod, 'Jun 2026');
  assert.equal(selection.previousPeriod, null);
  assert.equal(selection.previousIndex, null);
});

test('J: annual selection compares exact completed fiscal years', () => {
  const selection = selectStatementPeriods(['Mar 2023', 'Mar 2025', 'Mar 2026'], 'annual_flow');
  assert.equal(selection.currentPeriod, 'Mar 2026');
  assert.equal(selection.previousPeriod, 'Mar 2025');
});

test('K: TTM is excluded from completed-FY comparison and history', () => {
  const periods = ['Mar 2024', 'Mar 2025', 'Mar 2026', 'TTM'];
  const selection = selectStatementPeriods(periods, 'annual_flow');
  assert.equal(selection.currentPeriod, 'Mar 2026');
  assert.equal(selection.previousPeriod, 'Mar 2025');
  assert.deepEqual(selection.historyIndices.map(index => periods[index]), ['Mar 2024', 'Mar 2025', 'Mar 2026']);
});

test('L: borrowings growth is a neutral balance change', () => {
  const change = calculatePeriodChange('Borrowings', 120, 100);
  assert.equal(change?.label, '+20.0%');
  assert.equal(change?.tone, 'neutral');
  assert.equal(getMetricPresentation('Borrowings').direction, 'context_dependent');
});

test('M: deposit growth is neutral rather than an investment verdict', () => {
  const change = calculatePeriodChange('Deposits', 1100, 1000);
  assert.equal(change?.label, '+10.0%');
  assert.equal(change?.tone, 'neutral');
});

test('cash-flow comparison excludes TTM and requires an exact prior completed FY', () => {
  const periods = ['Mar 2024', 'Mar 2026', 'TTM'];
  const selection = selectStatementPeriods(periods, 'cash_flow');
  assert.equal(selection.currentPeriod, 'Mar 2026');
  assert.equal(selection.previousPeriod, null);
  assert.deepEqual(selection.historyIndices.map(index => periods[index]), ['Mar 2024', 'Mar 2026']);
});

test('missing values never become zero-valued changes', () => {
  assert.equal(calculatePeriodChange('Revenue', null, 100), null);
  assert.equal(calculatePeriodChange('Revenue', 100, null), null);
});

test('absolute costs use neutral tone without thresholds', () => {
  const change = calculatePeriodChange('Employee Cost', 90, 100);
  assert.equal(change?.label, '-10.0%');
  assert.equal(change?.tone, 'neutral');
});

test('UX A: an absolute Employee Cost increase is context-dependent and neutral', () => {
  const change = calculatePeriodChange('Employee Cost', 120, 100);
  assert.equal(getMetricPresentation('Employee Cost').direction, 'context_dependent');
  assert.equal(change?.label, '+20.0%');
  assert.equal(change?.tone, 'neutral');
});

test('UX B: Cost-to-Income increase uses bps and lower-is-better tone', () => {
  const change = calculatePeriodChange('Cost-to-Income', 55, 50);
  assert.equal(getMetricPresentation('Cost-to-Income').direction, 'lower_is_better');
  assert.equal(getMetricPresentation('Cost-to-Income %').direction, 'lower_is_better');
  assert.equal(change?.label, '+500 bps');
  assert.equal(change?.tone, 'negative');
});

test('UX C-D: GNPA decrease is positive while Borrowings increase remains neutral', () => {
  assert.equal(calculatePeriodChange('GNPA %', 2, 2.5)?.tone, 'positive');
  assert.equal(calculatePeriodChange('Borrowings', 120, 100)?.tone, 'neutral');
});

test('UX E-F: final-column comparison basis is explicit by statement type', () => {
  assert.equal(selectStatementPeriods(['Mar 2026', 'Jun 2026'], 'quarterly').comparisonBasisLabel, 'vs previous quarter');
  assert.equal(selectStatementPeriods(['Mar 2025', 'Mar 2026'], 'annual_flow').comparisonBasisLabel, 'vs previous FY');
  assert.equal(selectStatementPeriods(['Mar 2025', 'Mar 2026'], 'balance_sheet').comparisonBasisLabel, 'vs previous FY balance');
});

test('UX G-I: ratio deltas use bps and annual history remains TTM-safe', () => {
  assert.equal(calculatePeriodChange('OPM %', 20, 18)?.unit, 'basis points');
  const periods = ['Mar 2024', 'Mar 2025', 'Mar 2026', 'TTM'];
  const selection = selectStatementPeriods(periods, 'annual_flow');
  assert.equal(selection.currentPeriod, 'Mar 2026');
  assert.equal(selection.previousPeriod, 'Mar 2025');
  assert.deepEqual(selection.historyIndices.map(index => periods[index]), ['Mar 2024', 'Mar 2025', 'Mar 2026']);
});

test('UX J: expanded row-header help resolves common P&L, balance-sheet, cash-flow and bank rows', () => {
  const expected = {
    'Employee Cost': 'employee_cost',
    'Finance Cost': 'finance_cost',
    'Profit Before Tax': 'pbt',
    'Equity Capital': 'equity_capital',
    'Shareholders Funds': 'net_worth',
    'Total Assets': 'total_assets',
    'Cash from Investing Activity': 'investing_cash_flow',
    'Net Cash Flow': 'net_cash_flow',
    'Fixed Assets Purchased': 'capex',
    'NIM %': 'nim',
    'CASA Ratio': 'casa',
    'Cost-to-Income': 'cost_to_income',
    'Credit Cost': 'credit_cost'
  };
  for (const [row, glossaryTerm] of Object.entries(expected)) {
    assert.equal(getStatementGlossaryTerm(row), glossaryTerm, row);
  }
});

test('UX K-L: Standardized stays discoverable at low emphasis and key statuses remain explainable', () => {
  assert.equal(PROVENANCE_STATUS_PRESENTATION.standardized.emphasis, 'low');
  assert.equal(PROVENANCE_STATUS_PRESENTATION.standardized.glossaryTerm, 'standardized');
  for (const status of STOCKER_STATUS_GUIDE) {
    const item = glossary[status.glossaryTerm];
    assert.ok(item.meaning.length > 0, `${status.label} meaning`);
    assert.ok(item.whyItMatters.length > 0, `${status.label} implication`);
    assert.ok(item.userAction?.length > 0, `${status.label} user action`);
  }
});

test('UX M: help interactions retain accessible outside-click, Escape and focus behavior', () => {
  const conceptPanel = readFileSync(new URL('../src/components/ui/ConceptGuidePanel.tsx', import.meta.url), 'utf8');
  const dataOrigin = readFileSync(new URL('../src/components/ui/DataOriginBadge.tsx', import.meta.url), 'utf8');
  const statusGuide = readFileSync(new URL('../src/components/ui/StockerStatusGuide.tsx', import.meta.url), 'utf8');
  assert.match(conceptPanel, /onPointerDown/);
  assert.match(conceptPanel, /Escape/);
  assert.match(conceptPanel, /aria-modal="true"/);
  assert.match(conceptPanel, /<X /);
  assert.match(conceptPanel, /onClick=\{onClose\}/);
  assert.match(conceptPanel, /returnFocusRef/);
  assert.match(conceptPanel, /focusableSelector/);
  assert.match(conceptPanel, /document\.body\.style\.overflow = 'hidden'/);
  assert.match(dataOrigin, /pointerdown/);
  assert.match(dataOrigin, /Escape/);
  assert.match(statusGuide, /onPointerDown/);
  assert.match(statusGuide, /Escape/);
  assert.match(statusGuide, /aria-modal="true"/);
});

test('beginner guide: priority concepts always explain the term, relevance and Stocker usage', () => {
  const priority = [
    'revenue', 'expenses', 'operating_profit', 'ebitda', 'ebit', 'opm', 'pbt', 'pat', 'eps',
    'equity_capital', 'reserves', 'net_worth', 'borrowings', 'total_assets', 'working_capital', 'cwip',
    'cfo', 'investing_cash_flow', 'financing_cash_flow', 'capex', 'fcf', 'cfo_pat',
    'roe', 'roce', 'roa', 'asset_turnover', 'debt_equity', 'interest_coverage', 'current_ratio', 'net_profit_margin',
    'pe', 'pb', 'ev_ebitda', 'dividend_yield', 'fcf_yield', 'revenue_growth', 'profit_growth', 'sales_cagr', 'pat_cagr', 'qoq', 'yoy',
    'nim', 'deposits', 'advances', 'casa', 'gnpa', 'nnpa', 'credit_cost', 'cost_to_income', 'capital_adequacy', 'cet1',
    'reported_fact', 'stocker_calculation', 'ai_interpretation', 'standardized', 'verified', 'mixed', 'discrepancy',
    'provisional', 'evidence_enriched', 'stale', 'unavailable'
  ];
  assert.ok(glossaryEntries.length >= priority.length);
  for (const term of priority) {
    const guide = getFinancialConceptGuide(term);
    assert.ok(guide, `${term} exists`);
    assert.ok(guide.plainEnglish.trim().length > 0, `${term} plainEnglish`);
    assert.ok(guide.whyItMatters.trim().length > 0, `${term} whyItMatters`);
    assert.ok(guide.stockerUsage.trim().length > 0, `${term} stockerUsage`);
  }
});

test('beginner guide: formula metrics have a usable formula and explained inputs', () => {
  const formulaMetrics = [
    'eps', 'opm', 'sales_cagr', 'pat_cagr', 'qoq', 'yoy', 'cfo_pat', 'capex', 'fcf', 'roe', 'roce', 'roa',
    'debt_equity', 'interest_coverage', 'working_capital', 'current_ratio', 'asset_turnover', 'net_profit_margin',
    'pe', 'pb', 'ev_ebitda', 'dividend_yield', 'fcf_yield', 'revenue_growth', 'profit_growth', 'nim', 'casa', 'gnpa', 'nnpa',
    'cd_ratio', 'credit_cost', 'cost_to_income', 'capital_adequacy', 'cet1'
  ];
  for (const term of formulaMetrics) {
    const guide = glossary[term];
    assert.ok(guide.formula?.trim().length > 5, `${term} formula`);
    assert.ok(guide.formulaInputs?.length > 0, `${term} formula inputs`);
    assert.ok(guide.formulaInputs.every(input => input.label && input.meaning), `${term} valid formula inputs`);
  }
});

test('beginner guide: formula wording matches the current Stocker engines', () => {
  assert.match(glossary.cfo_pat.formula, /Cumulative CFO over 5 exact common completed FYs/i);
  assert.equal(glossary.fcf.formula, 'Cash from operations − Capital expenditure');
  assert.match(glossary.capex.formula, /Δ fixed assets \+ depreciation \+ Δ CWIP/i);
  assert.equal(glossary.debt_equity.formula, 'Total borrowings ÷ (equity capital + reserves)');
  assert.match(glossary.debt_equity.stockerUsage, /absent component contributes zero/i);
  assert.match(glossary.qoq.formula, /\|Previous quarter\|/);
  assert.match(glossary.yoy.formula, /\|Same period last year\|/);
  assert.match(glossary.sales_cagr.stockerUsage, /TTM is excluded/i);
  assert.match(glossary.pat_cagr.stockerUsage, /positive completed-FY PAT endpoints/i);
  assert.match(glossary.nim.stockerUsage, /reported NIM row.*does not derive NIM/i);
  assert.match(glossary.gnpa.stockerUsage, /preferring the latest quarterly statement/i);
  assert.match(glossary.nnpa.stockerUsage, /never derives NNPA from GNPA/i);
  assert.match(glossary.casa.stockerUsage, /does not reconstruct/i);
  assert.match(glossary.capital_adequacy.stockerUsage, /does not derive/i);
  assert.match(glossary.cet1.stockerUsage, /does not estimate/i);
  assert.match(glossary.ttm.stockerUsage, /excludes TTM/i);
});

test('beginner guide: key concepts have tiny numerical examples', () => {
  const examples = ['revenue', 'opm', 'eps', 'cfo', 'fcf', 'cfo_pat', 'roe', 'roce', 'roa', 'debt_equity', 'pe', 'nim', 'gnpa', 'credit_cost', 'cost_to_income'];
  for (const term of examples) {
    const example = glossary[term].practicalExample;
    assert.ok(example?.inputs.length, `${term} inputs`);
    assert.ok(example?.calculation.includes('='), `${term} arithmetic`);
    assert.ok(example?.takeaway.length, `${term} takeaway`);
  }
});

test('beginner guide: bank concepts and corporate FCF are business-model aware', () => {
  for (const term of ['nim', 'deposits', 'advances', 'casa', 'gnpa', 'nnpa', 'credit_cost', 'cost_to_income', 'capital_adequacy', 'cet1']) {
    const guide = glossary[term];
    assert.match(`${guide.plainEnglish} ${guide.whyItMatters} ${guide.interpretation.join(' ')}`, /bank|loan|deposit|advance|credit|regulatory/i, term);
  }
  const bankFcfNotes = getRelevantSectorNotes(glossary.fcf, { businessModel: 'BANK' });
  assert.match(bankFcfNotes.map(note => note.note).join(' '), /not a primary bank metric/i);
  const bankRoceNotes = getRelevantSectorNotes(glossary.roce, { businessModel: 'BANK' });
  assert.match(bankRoceNotes.map(note => note.note).join(' '), /not a primary bank metric/i);
  for (const term of ['nim', 'gnpa', 'nnpa', 'credit_cost', 'cost_to_income', 'roa', 'roe']) {
    const nbfcNotes = getRelevantSectorNotes(glossary[term], { businessModel: 'NBFC_LENDER' });
    assert.match(nbfcNotes.map(note => note.note).join(' '), /specialized.*not yet available/i, `${term} NBFC safety`);
  }
});

test('beginner guide: directional cautions stay context-dependent', () => {
  assert.match(glossary.roe.commonMistake, /leverage/i);
  assert.match(glossary.expenses.interpretation.join(' '), /not automatically bad/i);
  assert.match(glossary.roce.interpretation.join(' '), /history|same-sector|cost of capital/i);
});

test('beginner guide: no unsupported ROCE threshold boxes and unknown terms fail gracefully', () => {
  const source = readFileSync(new URL('../src/data/glossary.ts', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /ROCE[^\n]*(?:22%|14\s*[–-]\s*20%|<\s*10%)/i);
  assert.doesNotMatch(source, /(?:Great|Danger)\s*(?:ROCE|\d+%)/i);
  assert.equal(getFinancialConceptGuide('definitely_not_a_metric'), null);
});

test('beginner guide: provenance definitions follow the Engineering Contract categories', () => {
  assert.equal(glossary.verified.title, 'Officially Verified');
  assert.match(glossary.reported_fact.plainEnglish, /standardized reported financial statements|company disclosure/i);
  assert.match(glossary.reported_fact.stockerUsage, /unit and currency are compatible/i);
  assert.match(glossary.management_guidance.stockerUsage, /verbatim forward statements or targets/i);
  assert.match(glossary.stocker_calculation.plainEnglish, /calculated by Stocker/i);
  assert.match(glossary.stocker_projection.stockerUsage, /DCF scenarios|intrinsic-value estimates/i);
  assert.match(glossary.ai_interpretation.plainEnglish, /AI-generated/i);
  assert.match(glossary.standardized.plainEnglish, /has not been officially reconciled/i);
  assert.match(glossary.mixed.plainEnglish, /combination/i);
  assert.match(glossary.discrepancy.plainEnglish, /disagree/i);
  assert.match(glossary.unavailable.interpretation.join(' '), /not zero/i);
});

test('UX N: Stocker cash-flow analysis uses metrics as rows and periods as columns', () => {
  const table = buildCashFlowAnalysisTable([
    {
      period: 'Mar 2025', reported_pat_cr: 80, reported_cfo_cr: 100, cfo_to_pat_pct: 125,
      capex_cr: 30, stocker_derived_fcf_cr: 70, capex_methodology: 'Fixed assets purchased'
    },
    {
      period: 'Mar 2026', reported_pat_cr: 90, reported_cfo_cr: 120, cfo_to_pat_pct: 133.3,
      capex_cr: 35, stocker_derived_fcf_cr: 85, capex_methodology: 'Fixed assets purchased'
    }
  ]);
  assert.deepEqual(table.periods, ['Mar 2025', 'Mar 2026']);
  assert.deepEqual(table.rows.map(row => row.key), ['pat', 'cfo', 'cfo_pat', 'capex', 'fcf']);
  assert.deepEqual(table.rows.find(row => row.key === 'cfo')?.values, [100, 120]);
  assert.equal(table.rows.find(row => row.key === 'capex')?.origin, 'reported_or_derived');
  assert.equal(table.rows.find(row => row.key === 'fcf')?.origin, 'stocker_calculation');
});

test('Change / Trend column keeps the explicit basis beside the change and removes latest-cell duplication', () => {
  const source = readFileSync(new URL('../src/components/ui/FinancialStatementTable.tsx', import.meta.url), 'utf8');
  assert.match(source, /Change \/ Trend/);
  assert.match(source, /visibleComparisonLabel=\{selection\.comparisonBasisLabel\}/);
  assert.doesNotMatch(source, /showChange=\{isComparisonCurrent/);
});
