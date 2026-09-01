import test from 'node:test';
import assert from 'node:assert/strict';

import {
  calculatePeriodChange,
  getMetricPresentation,
  selectStatementPeriods
} from '../src/utils/financialMetrics.ts';

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

test('explicit costs use lower-is-better tone without thresholds', () => {
  const change = calculatePeriodChange('Employee Cost', 90, 100);
  assert.equal(change?.label, '-10.0%');
  assert.equal(change?.tone, 'positive');
});
