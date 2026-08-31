import React from 'react';
import { Bot, Calculator, FileCheck2, Sparkles, Target } from 'lucide-react';

export type DataOrigin =
  | 'reported_fact'
  | 'stocker_calculation'
  | 'management_guidance'
  | 'ai_interpretation'
  | 'stocker_projection';

const originConfig = {
  reported_fact: { label: 'Screener Standardized', icon: FileCheck2, className: 'origin-reported' },
  stocker_calculation: { label: 'Stocker Calculation', icon: Calculator, className: 'origin-calculation' },
  management_guidance: { label: 'Management Guidance', icon: Target, className: 'origin-guidance' },
  ai_interpretation: { label: 'AI Interpretation', icon: Bot, className: 'origin-ai' },
  stocker_projection: { label: 'Stocker Projection', icon: Sparkles, className: 'origin-projection' }
} as const;

interface DataOriginBadgeProps {
  origin: DataOrigin;
  className?: string;
  compact?: boolean;
}

export const DataOriginBadge: React.FC<DataOriginBadgeProps> = ({ origin, className = '', compact = false }) => {
  const config = originConfig[origin];
  const Icon = config.icon;

  return (
    <span className={`data-origin-badge ${config.className} ${className}`} title={config.label}>
      <Icon className="w-3 h-3" aria-hidden="true" />
      {!compact && <span>{config.label}</span>}
    </span>
  );
};
