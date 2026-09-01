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
import { glossary } from '../src/data/glossary.ts';
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

test('UX M: help interactions retain outside-click, Escape and viewport-close handlers', () => {
  const conceptHelp = readFileSync(new URL('../src/components/ui/ConceptHelp.tsx', import.meta.url), 'utf8');
  const dataOrigin = readFileSync(new URL('../src/components/ui/DataOriginBadge.tsx', import.meta.url), 'utf8');
  const statusGuide = readFileSync(new URL('../src/components/ui/StockerStatusGuide.tsx', import.meta.url), 'utf8');
  for (const source of [conceptHelp, dataOrigin]) {
    assert.match(source, /pointerdown/);
    assert.match(source, /Escape/);
    assert.match(source, /scroll/);
    assert.match(source, /resize/);
  }
  assert.match(statusGuide, /onPointerDown/);
  assert.match(statusGuide, /Escape/);
  assert.match(statusGuide, /aria-modal="true"/);
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
