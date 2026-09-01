import React, { useEffect, useRef, useState } from 'react';
import { Bot, Calculator, FileCheck2, Layers, Sparkles, Target } from 'lucide-react';

export type DataOrigin =
  | 'reported_fact'
  | 'reported_or_derived'
  | 'stocker_calculation'
  | 'management_guidance'
  | 'ai_interpretation'
  | 'stocker_projection';

const originConfig = {
  reported_fact: { label: 'Reported data', icon: FileCheck2, className: 'origin-reported', explanation: 'Financial statement data standardized by Screener. It remains discoverable here but is not officially reconciled unless a separate Verified badge says so.', action: 'Usually none. Open provenance details when official reconciliation matters.' },
  reported_or_derived: { label: 'Reported / derived input', icon: Layers, className: 'origin-calculation', explanation: 'Stocker uses the reported capex line when it is available; otherwise it may derive the input from statement movements using the method shown for that period.', action: 'Open the period methodology or Formula & Inputs when the distinction matters.' },
  stocker_calculation: { label: 'Stocker Calculation', icon: Calculator, className: 'origin-calculation', explanation: 'Calculated deterministically by Stocker from visible financial inputs and a defined formula.', action: 'Inspect Formula & Inputs before relying on a material result.' },
  management_guidance: { label: 'Management Guidance', icon: Target, className: 'origin-guidance', explanation: 'A forward-looking statement made by company management, not a reported result or guarantee.', action: 'Check the cited filing and track later delivery.' },
  ai_interpretation: { label: 'AI Interpretation', icon: Bot, className: 'origin-ai', explanation: 'AI-assisted interpretation of company documents. Important conclusions should be checked against cited sources.', action: 'Verify important findings against the linked filing.' },
  stocker_projection: { label: 'Stocker Projection', icon: Sparkles, className: 'origin-projection', explanation: 'A Stocker scenario based on stated assumptions and available evidence, not a company-reported fact.', action: 'Review assumptions and evidence before using the scenario.' }
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
  const rootRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => event.key === 'Escape' && setOpen(false);
    const closeOnOutsidePress = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnViewportChange = () => setOpen(false);
    window.addEventListener('keydown', closeOnEscape);
    window.addEventListener('pointerdown', closeOnOutsidePress);
    window.addEventListener('resize', closeOnViewportChange);
    window.addEventListener('scroll', closeOnViewportChange, true);
    return () => {
      window.removeEventListener('keydown', closeOnEscape);
      window.removeEventListener('pointerdown', closeOnOutsidePress);
      window.removeEventListener('resize', closeOnViewportChange);
      window.removeEventListener('scroll', closeOnViewportChange, true);
    };
  }, [open]);

  return (
    <span ref={rootRef} className="relative inline-flex">
      <button
        type="button"
        className={`data-origin-badge ${config.className} ${className}`}
        title={`${config.label} — open source explanation`}
        aria-label={`${config.label} data origin. Open explanation.`}
        aria-expanded={open}
        onClick={(event) => { event.stopPropagation(); setOpen(value => !value); }}
      >
        <Icon className="w-3 h-3" aria-hidden="true" />
        {!compact && <span>{config.label}</span>}
      </button>
      {open && (
        <span role="tooltip" className="fixed inset-x-4 bottom-4 z-40 rounded-lg border border-slate-700 bg-slate-950 p-2.5 text-left text-[11px] font-normal leading-relaxed text-slate-300 shadow-xl sm:absolute sm:inset-x-auto sm:bottom-auto sm:left-0 sm:top-full sm:mt-2 sm:w-64">
          <strong className="mb-1 block text-slate-100">Data source: {config.label}</strong>
          <span>{config.explanation}</span>
          <span className="mt-1.5 block text-slate-400"><strong>What to do:</strong> {config.action}</span>
        </span>
      )}
    </span>
  );
};
