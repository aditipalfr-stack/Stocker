export type MetricDirection = 'higher_is_better' | 'lower_is_better' | 'context_dependent' | 'neutral';
export type TrendTone = 'positive' | 'negative' | 'warning' | 'neutral';
export type MetricImportance = 'core' | 'supporting' | 'standard';
export type FinancialStatementKind = 'quarterly' | 'annual_flow' | 'balance_sheet' | 'cash_flow';
export type FinancialPeriodKind = 'quarterly' | 'annual_completed' | 'ttm' | 'unknown';

export interface MetricPresentation {
  direction: MetricDirection;
  importance: MetricImportance;
  changeUnit: 'percent' | 'basis_points';
  negativeResultIsBad: boolean;
  showSparkline: boolean;
}

const DEFAULT_PRESENTATION: MetricPresentation = {
  direction: 'context_dependent',
  importance: 'standard',
  changeUnit: 'percent',
  negativeResultIsBad: false,
  showSparkline: false
};

const METRIC_RULES: Array<{ matches: (metric: string) => boolean; presentation: MetricPresentation }> = [
  {
    matches: metric => /^(gross npa|gross npa %|gnpa|gnpa %|net npa|net npa %|nnpa|nnpa %)$/.test(metric),
    presentation: { direction: 'lower_is_better', importance: 'core', changeUnit: 'basis_points', negativeResultIsBad: false, showSparkline: true }
  },
  {
    matches: metric => /^(sales|revenue|revenue from operations|total income)$/.test(metric),
    presentation: { direction: 'higher_is_better', importance: 'core', changeUnit: 'percent', negativeResultIsBad: true, showSparkline: true }
  },
  {
    matches: metric => /^(operating profit|ebitda)$/.test(metric),
    presentation: { direction: 'higher_is_better', importance: 'core', changeUnit: 'percent', negativeResultIsBad: true, showSparkline: true }
  },
  {
    matches: metric => /^(opm|opm %|operating profit margin|ebitda margin)$/.test(metric),
    presentation: { direction: 'higher_is_better', importance: 'core', changeUnit: 'basis_points', negativeResultIsBad: true, showSparkline: true }
  },
  {
    matches: metric => /^(net profit|pat|profit after tax|net income)$/.test(metric),
    presentation: { direction: 'higher_is_better', importance: 'core', changeUnit: 'percent', negativeResultIsBad: true, showSparkline: true }
  },
  {
    matches: metric => /^eps(?:\s|$)/.test(metric),
    presentation: { direction: 'higher_is_better', importance: 'supporting', changeUnit: 'percent', negativeResultIsBad: true, showSparkline: false }
  },
  {
    matches: metric => /^(cash from operating activity|cash from operations|operating cash flow|cfo)$/.test(metric),
    presentation: { direction: 'higher_is_better', importance: 'core', changeUnit: 'percent', negativeResultIsBad: true, showSparkline: true }
  },
  {
    matches: metric => /^(free cash flow|fcf)$/.test(metric),
    presentation: { direction: 'higher_is_better', importance: 'core', changeUnit: 'percent', negativeResultIsBad: true, showSparkline: true }
  },
  {
    matches: metric => /^(roe|roe %|roce|roce %|return on equity|return on capital employed)$/.test(metric),
    presentation: { direction: 'higher_is_better', importance: 'supporting', changeUnit: 'basis_points', negativeResultIsBad: true, showSparkline: false }
  },
  {
    matches: metric => /^(cost[- ]to[- ]income(?: ratio)?|credit cost(?: ratio)?)(?: %)?$/.test(metric),
    presentation: { direction: 'lower_is_better', importance: 'supporting', changeUnit: 'basis_points', negativeResultIsBad: false, showSparkline: true }
  },
  {
    matches: metric => /^(roa|roa %|return on assets|nim|nim %|net interest margin|capital adequacy ratio|car)$/.test(metric),
    presentation: { direction: 'context_dependent', importance: 'supporting', changeUnit: 'basis_points', negativeResultIsBad: false, showSparkline: false }
  },
  {
    matches: metric => /^(expenses|total expenses|operating expenses|employee cost|material cost|cost of materials consumed|cost of goods sold|finance cost|finance costs|interest expense|interest expended)$/.test(metric),
    presentation: { direction: 'context_dependent', importance: 'supporting', changeUnit: 'percent', negativeResultIsBad: false, showSparkline: true }
  },
  {
    matches: metric => /(borrowings|\bdebt\b|inventory|receivables|debtors|working capital|capex|capital expenditure|fixed assets purchased|cwip|capital work in progress|p\/e|total assets|deposits|advances|loans and advances|loans & advances)/.test(metric),
    presentation: { direction: 'context_dependent', importance: 'supporting', changeUnit: 'percent', negativeResultIsBad: false, showSparkline: false }
  },
  {
    matches: metric => /^(credit.deposit ratio|cd ratio|c\/d ratio)$/.test(metric),
    presentation: { direction: 'context_dependent', importance: 'supporting', changeUnit: 'basis_points', negativeResultIsBad: false, showSparkline: false }
  }
];

export const normalizeMetricName = (metric: string) => metric.trim().toLowerCase().replace(/\s+/g, ' ');

export const getMetricPresentation = (metric: string): MetricPresentation => {
  const normalized = normalizeMetricName(metric);
  const matched = METRIC_RULES.find(rule => rule.matches(normalized))?.presentation;
  if (matched) return matched;
  if (normalized.includes('%') || normalized.includes('margin')) {
    return { ...DEFAULT_PRESENTATION, changeUnit: 'basis_points' };
  }
  return DEFAULT_PRESENTATION;
};

interface ParsedFinancialPeriod {
  kind: FinancialPeriodKind;
  canonicalKey: string | null;
  ordinal: number | null;
}

const TTM_PERIODS = new Set([
  'TTM', 'LTM', 'TRAILING 12 MONTHS', 'TRAILING TWELVE MONTHS', 'TRAIL. 12M', 'TRAIL 12M'
]);

const parseYear = (rawYear: string): number => {
  const year = Number(rawYear);
  return rawYear.length <= 2 ? 2000 + year : year;
};

const quarterPeriod = (calendarYear: number, quarter: number): ParsedFinancialPeriod => ({
  kind: 'quarterly',
  canonicalKey: `${calendarYear}-Q${quarter}`,
  ordinal: calendarYear * 12 + [0, 6, 9, 12, 3][quarter]
});

/** Mirrors the backend's fiscal-quarter normalization while using the statement
 * kind to disambiguate labels such as "Mar 2026" (Q4 in a quarterly table,
 * completed FY in an annual table).
 */
export const parseFinancialPeriod = (period: string, statementKind: FinancialStatementKind): ParsedFinancialPeriod => {
  const clean = String(period || '').trim().toUpperCase();
  if (!clean) return { kind: 'unknown', canonicalKey: null, ordinal: null };
  if (TTM_PERIODS.has(clean)) return { kind: 'ttm', canonicalKey: 'TTM', ordinal: null };

  if (statementKind === 'quarterly') {
    const canonical = clean.match(/^(\d{4})-Q([1-4])$/);
    if (canonical) return quarterPeriod(Number(canonical[1]), Number(canonical[2]));

    const fiscalQuarter = clean.match(/Q([1-4])\s*(?:FY)?\s*(\d{2,4})/);
    if (fiscalQuarter) {
      const quarter = Number(fiscalQuarter[1]);
      const fiscalYear = parseYear(fiscalQuarter[2]);
      return quarterPeriod(quarter === 4 ? fiscalYear : fiscalYear - 1, quarter);
    }

    const monthYear = clean.match(/\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s*[-/,.]?\s*(\d{4})\b/);
    if (monthYear) {
      const quarterByMonth: Record<string, number> = { JUN: 1, SEP: 2, DEC: 3, MAR: 4 };
      const quarter = quarterByMonth[monthYear[1].slice(0, 3)];
      if (quarter) return quarterPeriod(Number(monthYear[2]), quarter);
    }

    const numericDate = clean.match(/\b\d{1,2}[-/.](\d{2})[-/.](\d{4})\b/);
    if (numericDate) {
      const quarterByMonth: Record<string, number> = { '06': 1, '09': 2, '12': 3, '03': 4 };
      const quarter = quarterByMonth[numericDate[1]];
      if (quarter) return quarterPeriod(Number(numericDate[2]), quarter);
    }

    return { kind: 'unknown', canonicalKey: null, ordinal: null };
  }

  const canonicalAnnual = clean.match(/^(\d{4})-FY$/);
  const fiscalYear = clean.match(/^FY\s*(\d{2,4})$/);
  const annualPhraseYear = clean.match(/(?:YEAR ENDED|FULL[- ]YEAR|ANNUAL|12M).*?(\d{4})/);
  const monthYear = clean.match(/\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s*[-/,.]?\s*(\d{4})\b/);
  const year = canonicalAnnual
    ? Number(canonicalAnnual[1])
    : fiscalYear
      ? parseYear(fiscalYear[1])
      : annualPhraseYear
        ? Number(annualPhraseYear[1])
        : monthYear
          ? Number(monthYear[1])
          : null;

  return year === null
    ? { kind: 'unknown', canonicalKey: null, ordinal: null }
    : { kind: 'annual_completed', canonicalKey: `${year}-FY`, ordinal: year };
};

const priorQuarterCanonicalKey = (canonicalKey: string): string | null => {
  const match = canonicalKey.match(/^(\d{4})-Q([1-4])$/);
  if (!match) return null;
  const year = Number(match[1]);
  const quarter = Number(match[2]);
  if (quarter === 1) return `${year}-Q4`;
  if (quarter === 2) return `${year}-Q1`;
  if (quarter === 3) return `${year}-Q2`;
  return `${year - 1}-Q3`;
};

export interface StatementPeriodSelection {
  currentIndex: number | null;
  previousIndex: number | null;
  currentPeriod: string | null;
  previousPeriod: string | null;
  historyIndices: number[];
  comparisonLabel: string;
  comparisonBasisLabel: string;
  historyLabel: string;
}

export const selectStatementPeriods = (
  periods: string[],
  statementKind: FinancialStatementKind
): StatementPeriodSelection => {
  const expectedKind: FinancialPeriodKind = statementKind === 'quarterly' ? 'quarterly' : 'annual_completed';
  const compatible = periods
    .map((period, index) => ({ period, index, parsed: parseFinancialPeriod(period, statementKind) }))
    .filter(item => item.parsed.kind === expectedKind && item.parsed.canonicalKey !== null && item.parsed.ordinal !== null)
    .sort((a, b) => (a.parsed.ordinal as number) - (b.parsed.ordinal as number) || a.index - b.index);

  const current = compatible[compatible.length - 1] ?? null;
  const priorCanonical = current?.parsed.canonicalKey
    ? statementKind === 'quarterly'
      ? priorQuarterCanonicalKey(current.parsed.canonicalKey)
      : `${(current.parsed.ordinal as number) - 1}-FY`
    : null;
  const previous = priorCanonical
    ? [...compatible].reverse().find(item => item.parsed.canonicalKey === priorCanonical) ?? null
    : null;

  const labels: Record<FinancialStatementKind, { comparison: string; basis: string; history: string }> = {
    quarterly: { comparison: 'QoQ · exact prior quarter', basis: 'vs previous quarter', history: 'quarterly periods' },
    annual_flow: { comparison: 'FY change · prior completed FY', basis: 'vs previous FY', history: 'completed FY only' },
    balance_sheet: { comparison: 'balance change · prior FY', basis: 'vs previous FY balance', history: 'completed FY balances' },
    cash_flow: { comparison: 'FY change · prior completed FY', basis: 'vs previous FY', history: 'completed FY only' }
  };

  return {
    currentIndex: current?.index ?? null,
    previousIndex: previous?.index ?? null,
    currentPeriod: current?.period ?? null,
    previousPeriod: previous?.period ?? null,
    historyIndices: compatible.map(item => item.index),
    comparisonLabel: labels[statementKind].comparison,
    comparisonBasisLabel: labels[statementKind].basis,
    historyLabel: labels[statementKind].history
  };
};

export interface PeriodChange {
  rawDelta: number;
  percentChange: number | null;
  label: string;
  arrow: '↑' | '↓' | '→';
  tone: TrendTone;
  unit: 'percent change' | 'basis points' | 'state transition';
  formula: string;
  accessibleLabel: string;
}

const toneForDirection = (direction: MetricDirection, rawDelta: number): TrendTone => {
  if (Math.abs(rawDelta) < 1e-9 || direction === 'neutral' || direction === 'context_dependent') return 'neutral';
  if (direction === 'higher_is_better') return rawDelta > 0 ? 'positive' : 'negative';
  return rawDelta < 0 ? 'positive' : 'negative';
};

const isProfitMetric = (metric: string) => /^(operating profit|net profit|pat|profit after tax|net income|ebitda)$/.test(normalizeMetricName(metric));

export const calculatePeriodChange = (
  metric: string,
  current: number | null | undefined,
  previous: number | null | undefined
): PeriodChange | null => {
  if (typeof current !== 'number' || !Number.isFinite(current) || typeof previous !== 'number' || !Number.isFinite(previous)) return null;

  const presentation = getMetricPresentation(metric);
  const rawDelta = current - previous;
  const arrow = Math.abs(rawDelta) < 1e-9 ? '→' : rawDelta > 0 ? '↑' : '↓';
  const tone = toneForDirection(presentation.direction, rawDelta);

  if (presentation.changeUnit === 'basis_points') {
    const basisPoints = rawDelta * 100;
    const signed = basisPoints > 0 ? '+' : '';
    const label = Math.abs(basisPoints) < 0.05 ? 'Flat' : `${signed}${basisPoints.toFixed(0)} bps`;
    return {
      rawDelta,
      percentChange: null,
      label,
      arrow,
      tone,
      unit: 'basis points',
      formula: '(current ratio − prior ratio) × 100',
      accessibleLabel: `${label}, ${rawDelta > 0 ? 'increased' : rawDelta < 0 ? 'decreased' : 'unchanged'}`
    };
  }

  let transitionLabel: string | null = null;
  if (previous < 0 && current > 0) transitionLabel = isProfitMetric(metric) ? 'Turned profitable' : 'Turned positive';
  if (previous > 0 && current < 0) transitionLabel = 'Turned negative';
  if (Math.abs(previous) < 1e-9) transitionLabel = Math.abs(current) < 1e-9 ? 'Flat' : 'From zero';

  if (transitionLabel) {
    return {
      rawDelta,
      percentChange: null,
      label: transitionLabel,
      arrow,
      tone,
      unit: 'state transition',
      formula: 'sign/zero transition; percentage change is not calculated',
      accessibleLabel: transitionLabel
    };
  }

  const percentChange = (rawDelta / Math.abs(previous)) * 100;
  const label = Math.abs(percentChange) < 0.05
    ? 'Flat'
    : `${percentChange > 0 ? '+' : ''}${percentChange.toFixed(1)}%`;

  return {
    rawDelta,
    percentChange,
    label,
    arrow,
    tone,
    unit: 'percent change',
    formula: '(current − prior) ÷ |prior| × 100',
    accessibleLabel: `${label}, ${rawDelta > 0 ? 'increased' : rawDelta < 0 ? 'decreased' : 'unchanged'}`
  };
};

export const isGenuinelyNegativeResult = (metric: string, value: number | null | undefined) =>
  typeof value === 'number' && Number.isFinite(value) && value < 0 && getMetricPresentation(metric).negativeResultIsBad;

export const formatFinancialValue = (metric: string, value: number | null | undefined): string => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  const normalized = normalizeMetricName(metric);
  if (getMetricPresentation(metric).changeUnit === 'basis_points' || normalized.includes('%') || normalized.includes('margin')) {
    return `${value.toLocaleString('en-IN')}%`;
  }
  if (normalized.startsWith('eps')) return `₹${value.toLocaleString('en-IN')}`;
  return value.toLocaleString('en-IN');
};

export type ComparisonMetricKey = 'composite_score' | 'roce_pct' | 'fcf_yield_pct' | 'debt_to_equity';

export const COMPARISON_DIRECTION_RULES: Record<ComparisonMetricKey, MetricDirection> = {
  composite_score: 'higher_is_better',
  roce_pct: 'higher_is_better',
  fcf_yield_pct: 'higher_is_better',
  debt_to_equity: 'lower_is_better'
};

export type ComparisonStanding = 'best' | 'weakest' | 'standard';

export const getComparisonStanding = (
  metric: ComparisonMetricKey,
  value: number | null | undefined,
  allValues: Array<number | null | undefined>
): ComparisonStanding => {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'standard';
  const values = allValues.filter((candidate): candidate is number => typeof candidate === 'number' && Number.isFinite(candidate));
  if (values.length < 2 || Math.max(...values) === Math.min(...values)) return 'standard';

  const direction = COMPARISON_DIRECTION_RULES[metric];
  const best = direction === 'lower_is_better' ? Math.min(...values) : Math.max(...values);
  const weakest = direction === 'lower_is_better' ? Math.max(...values) : Math.min(...values);
  if (value === best) return 'best';
  if (value === weakest) return 'weakest';
  return 'standard';
};
