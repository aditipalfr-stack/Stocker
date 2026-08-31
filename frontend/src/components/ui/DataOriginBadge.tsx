import React, { useState } from 'react';
import { Bot, Calculator, FileCheck2, Sparkles, Target } from 'lucide-react';

export type DataOrigin =
  | 'reported_fact'
  | 'stocker_calculation'
  | 'management_guidance'
  | 'ai_interpretation'
  | 'stocker_projection';

const originConfig = {
  reported_fact: { label: 'Screener Standardized', icon: FileCheck2, className: 'origin-reported', explanation: 'Reported financial statement data standardized by Screener. Official reconciliation is shown separately by the provenance badge.' },
  stocker_calculation: { label: 'Stocker Calculation', icon: Calculator, className: 'origin-calculation', explanation: 'Calculated deterministically by Stocker from visible financial inputs and a defined formula.' },
  management_guidance: { label: 'Management Guidance', icon: Target, className: 'origin-guidance', explanation: 'A forward-looking statement made by company management, not a reported result or guarantee.' },
  ai_interpretation: { label: 'AI Interpretation', icon: Bot, className: 'origin-ai', explanation: 'AI-assisted interpretation of company documents. Important conclusions should be checked against cited sources.' },
  stocker_projection: { label: 'Stocker Projection', icon: Sparkles, className: 'origin-projection', explanation: 'A Stocker scenario based on stated assumptions and available evidence, not a company-reported fact.' }
} as const;

interface DataOriginBadgeProps {
  origin: DataOrigin;
  className?: string;
  compact?: boolean;
}

export const DataOriginBadge: React.FC<DataOriginBadgeProps> = ({ origin, className = '', compact = false }) => {
  const config = originConfig[origin];
  const Icon = config.icon;
  const [open, setOpen] = useState(false);

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        className={`data-origin-badge ${config.className} ${className}`}
        title={`${config.label} — open source explanation`}
        aria-label={`${config.label} data origin. Open explanation.`}
        aria-expanded={open}
        onClick={(event) => { event.stopPropagation(); setOpen(value => !value); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
      >
        <Icon className="w-3 h-3" aria-hidden="true" />
        {!compact && <span>{config.label}</span>}
      </button>
      {open && (
        <span role="tooltip" className="fixed inset-x-4 bottom-4 z-40 rounded-lg border border-slate-700 bg-slate-950 p-2.5 text-left text-[11px] font-normal leading-relaxed text-slate-300 shadow-xl sm:absolute sm:inset-x-auto sm:bottom-auto sm:left-0 sm:top-full sm:mt-2 sm:w-64">
          <strong className="mb-1 block text-slate-100">Data source: {config.label}</strong>
          {config.explanation}
        </span>
      )}
    </span>
  );
};
