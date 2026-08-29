import React from 'react';
import type { TrendTone } from '../../utils/financialMetrics';

interface SparklineProps {
  values: Array<number | null | undefined>;
  label: string;
  tone?: TrendTone;
  className?: string;
}

export const Sparkline: React.FC<SparklineProps> = ({ values, label, tone = 'neutral', className = '' }) => {
  const points = values
    .map((value, index) => ({ value, index }))
    .filter((point): point is { value: number; index: number } => typeof point.value === 'number' && Number.isFinite(point.value));

  if (points.length < 2) return <span className={`sparkline-empty ${className}`} aria-label={`${label}: not enough data`}>—</span>;

  const width = 92;
  const height = 28;
  const padding = 3;
  const min = Math.min(...points.map(point => point.value));
  const max = Math.max(...points.map(point => point.value));
  const range = max - min || 1;
  const xFor = (index: number) => padding + (index / Math.max(values.length - 1, 1)) * (width - padding * 2);
  const yFor = (value: number) => height - padding - ((value - min) / range) * (height - padding * 2);
  const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${xFor(point.index).toFixed(1)} ${yFor(point.value).toFixed(1)}`).join(' ');
  const last = points[points.length - 1];
  const crossesZero = min < 0 && max > 0;

  return (
    <svg className={`sparkline sparkline-${tone} ${className}`} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label}: ${points.map(point => point.value).join(', ')}`}>
      {crossesZero && <line x1={padding} x2={width - padding} y1={yFor(0)} y2={yFor(0)} className="sparkline-zero" />}
      <path d={path} fill="none" className="sparkline-path" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={xFor(last.index)} cy={yFor(last.value)} r="2.4" className="sparkline-end" />
    </svg>
  );
};
