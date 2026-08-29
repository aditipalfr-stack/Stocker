import React from 'react';
import {
  calculatePeriodChange,
  formatFinancialValue,
  getMetricPresentation,
  isGenuinelyNegativeResult
} from '../../utils/financialMetrics';
import type { TrendTone } from '../../utils/financialMetrics';

const toneClasses: Record<TrendTone, string> = {
  positive: 'trend-positive',
  negative: 'trend-negative',
  warning: 'trend-warning',
  neutral: 'trend-neutral'
};

interface ChangeIndicatorProps {
  metric: string;
  current: number | null | undefined;
  previous: number | null | undefined;
  className?: string;
}

export const ChangeIndicator: React.FC<ChangeIndicatorProps> = ({ metric, current, previous, className = '' }) => {
  const change = calculatePeriodChange(metric, current, previous);
  if (!change) return null;

  const contextual = getMetricPresentation(metric).direction === 'context_dependent';
  return (
    <span className={`change-indicator ${toneClasses[change.tone]} ${className}`} aria-label={`${contextual ? 'Context-dependent change: ' : ''}${change.accessibleLabel}`}>
      <span>{change.label}</span>
      <span aria-hidden="true">{change.arrow}</span>
      {contextual && <span className="change-context">Neutral</span>}
    </span>
  );
};

interface ExplicitChangeIndicatorProps {
  value: number | null | undefined;
  unit?: '%' | 'bps';
  direction?: 'higher_is_better' | 'lower_is_better' | 'neutral';
  label?: string;
}

export const ExplicitChangeIndicator: React.FC<ExplicitChangeIndicatorProps> = ({
  value,
  unit = '%',
  direction = 'higher_is_better',
  label
}) => {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  const arrow = Math.abs(value) < 1e-9 ? '→' : value > 0 ? '↑' : '↓';
  const tone: TrendTone = direction === 'neutral' || Math.abs(value) < 1e-9
    ? 'neutral'
    : direction === 'higher_is_better'
      ? value > 0 ? 'positive' : 'negative'
      : value < 0 ? 'positive' : 'negative';
  const formatted = `${value > 0 ? '+' : ''}${unit === 'bps' ? value.toFixed(0) : value.toFixed(1)}${unit}`;

  return (
    <span className={`change-indicator ${toneClasses[tone]}`} aria-label={`${label ? `${label}: ` : ''}${formatted}, ${value > 0 ? 'increased' : value < 0 ? 'decreased' : 'unchanged'}`}>
      {label && <span>{label}</span>}
      <span>{formatted}</span>
      <span aria-hidden="true">{arrow}</span>
    </span>
  );
};

interface FinancialMetricCellProps {
  metric: string;
  value: number | null | undefined;
  previous?: number | null;
  showChange?: boolean;
  className?: string;
}

export const FinancialMetricCell: React.FC<FinancialMetricCellProps> = ({ metric, value, previous, showChange = false, className = '' }) => {
  const negativeResult = isGenuinelyNegativeResult(metric, value);
  return (
    <div className={`financial-metric-cell ${className}`}>
      <span className={negativeResult ? 'financial-value-negative' : 'financial-value'}>
        {formatFinancialValue(metric, value)}
        {negativeResult && <span className="sr-only"> negative financial result</span>}
      </span>
      {showChange && <ChangeIndicator metric={metric} current={value} previous={previous} />}
    </div>
  );
};

export const trendToneFromValues = (metric: string, current?: number | null, previous?: number | null): TrendTone =>
  calculatePeriodChange(metric, current, previous)?.tone ?? 'neutral';
