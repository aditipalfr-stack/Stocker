export type MetricDirection = 'higher_is_better' | 'lower_is_better' | 'context_dependent' | 'neutral';
export type TrendTone = 'positive' | 'negative' | 'warning' | 'neutral';
export type MetricImportance = 'core' | 'supporting' | 'standard';

export interface MetricPresentation {
  direction: MetricDirection;
  importance: MetricImportance;
  changeUnit: 'percent' | 'basis_points';
  negativeResultIsBad: boolean;
  showSparkline: boolean;
}

const DEFAULT_PRESENTATION: MetricPresentation = {
  direction: 'neutral',
  importance: 'standard',
  changeUnit: 'percent',
  negativeResultIsBad: false,
  showSparkline: false
};
const METRIC_RULES: Array<{ matches: (metric: string) => boolean; presentation: MetricPresentation }> = [
  {
    matches: metric => /^(sales|revenue)$/.test(metric),
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
    matches: metric => /^(net profit|pat|profit after tax)$/.test(metric),
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
    matches: metric => /^(roe|roe %|roce|roce %)$/.test(metric),
    presentation: { direction: 'higher_is_better', importance: 'supporting', changeUnit: 'basis_points', negativeResultIsBad: true, showSparkline: false }
  },
  {
    matches: metric => /(borrowings|debt|inventory|receivables|debtors|working capital|capex|capital expenditure|fixed assets purchased|cwip|capital work in progress|p\/e|total assets)/.test(metric),
    presentation: { direction: 'context_dependent', importance: 'supporting', changeUnit: 'percent', negativeResultIsBad: false, showSparkline: false }
  }
];

export const normalizeMetricName = (metric: string) => metric.trim().toLowerCase().replace(/\s+/g, ' ');

export const getMetricPresentation = (metric: string): MetricPresentation => {
  const normalized = normalizeMetricName(metric);
  return METRIC_RULES.find(rule => rule.matches(normalized))?.presentation ?? DEFAULT_PRESENTATION;
};

export interface PeriodChange {
  rawDelta: number;
  percentChange: number | null;
  label: string;
  arrow: '↑' | '↓' | '→';
  tone: TrendTone;
  accessibleLabel: string;
}

const toneForDirection = (direction: MetricDirection, rawDelta: number): TrendTone => {
  if (Math.abs(rawDelta) < 1e-9 || direction === 'neutral' || direction === 'context_dependent') return 'neutral';
  if (direction === 'higher_is_better') return rawDelta > 0 ? 'positive' : 'negative';
  return rawDelta < 0 ? 'positive' : 'negative';
};

export const calculatePeriodChange = (
  metric: string,
  current: number | null | undefined,
  previous: number | null | undefined
): PeriodChange | null => {
  if (current === null || current === undefined || previous === null || previous === undefined) return null;

  const presentation = getMetricPresentation(metric);
  if (presentation.direction === 'neutral') return null;

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
      accessibleLabel: `${label}, ${rawDelta > 0 ? 'increased' : rawDelta < 0 ? 'decreased' : 'unchanged'}`
    };
  }

  if (Math.abs(previous) < 1e-9) {
    const label = Math.abs(rawDelta) < 1e-9 ? 'Flat' : 'From zero';
    return {
      rawDelta,
      percentChange: null,
      label,
      arrow,
      tone,
      accessibleLabel: `${label}, ${rawDelta > 0 ? 'increased' : rawDelta < 0 ? 'decreased' : 'unchanged'}`
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
    accessibleLabel: `${label}, ${rawDelta > 0 ? 'increased' : rawDelta < 0 ? 'decreased' : 'unchanged'}`
  };
};

export const isGenuinelyNegativeResult = (metric: string, value: number | null | undefined) =>
  typeof value === 'number' && value < 0 && getMetricPresentation(metric).negativeResultIsBad;

export const formatFinancialValue = (metric: string, value: number | null | undefined): string => {
  if (value === null || value === undefined) return '—';
  const normalized = normalizeMetricName(metric);
  if (normalized.includes('%') || normalized.includes('margin') || /^(roe|roce|opm)$/.test(normalized)) return `${value.toLocaleString('en-IN')}%`;
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
