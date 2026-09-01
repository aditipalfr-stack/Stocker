import React, { useEffect, useRef, useState } from 'react';
import { CheckCircle2, FileText, Layers, AlertTriangle, HelpCircle, ExternalLink, X } from 'lucide-react';
import type { AnalyticValueWithProvenance, AnalyticInputProvenance } from '../../types';
import { glossary } from '../../data/glossary';
import { PROVENANCE_STATUS_PRESENTATION, resolveProvenanceStatusKind } from '../../data/statusGuide';

interface FinancialProvenanceBadgeProps {
  provenance?: AnalyticValueWithProvenance | AnalyticInputProvenance | null;
  compact?: boolean;
  className?: string;
}

const formatInputMetricValue = (value: number | null | undefined, unit?: string, currency?: string): string => {
  if (value === null || value === undefined) return '—';
  if (unit === '%') return `${value.toFixed(1)}%`;
  if (unit === '₹ / Share' || unit === '₹/Share') return `₹${value.toFixed(2)} / Share`;
  if (unit === '₹ Cr' || unit === 'Cr') return `₹${value.toLocaleString()} Cr`;
  if (unit === 'Unknown') return `${value.toLocaleString()}`;
  if (currency && currency !== 'INR' && currency !== 'Unknown') {
    return `${currency} ${value.toLocaleString()} (${unit || 'amount'})`;
  }
  if (unit) return `${value.toLocaleString()} ${unit}`;
  return `₹${value.toLocaleString()} Cr`;
};

export const FinancialProvenanceBadge: React.FC<FinancialProvenanceBadgeProps> = ({
  provenance,
  compact = false,
  className = ''
}) => {
  const [showModal, setShowModal] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!showModal) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const focusTimer = window.setTimeout(() => closeRef.current?.focus(), 0);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setShowModal(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      window.removeEventListener('keydown', onKeyDown);
      (previouslyFocused || triggerRef.current)?.focus();
    };
  }, [showModal]);

  if (!provenance) return null;

  // Normalize provenance whether it's AnalyticValueWithProvenance or AnalyticInputProvenance
  const isValueWithProvenance = 'quality' in provenance;
  const quality = isValueWithProvenance 
    ? (provenance as AnalyticValueWithProvenance).quality 
    : ((provenance as AnalyticInputProvenance).verification_status === 'VERIFIED' 
        ? 'verified' 
        : (provenance as AnalyticInputProvenance).verification_status === 'DISCREPANCY' 
          ? 'discrepant' 
          : 'standardized');
  
  const hasDiscrepancy = isValueWithProvenance 
    ? (provenance as AnalyticValueWithProvenance).has_discrepancy 
    : (provenance as AnalyticInputProvenance).has_discrepancy;

  const inputs: AnalyticInputProvenance[] = isValueWithProvenance
    ? ((provenance as AnalyticValueWithProvenance).inputs || [])
    : [provenance as AnalyticInputProvenance];

  const statusKind = resolveProvenanceStatusKind(quality, hasDiscrepancy);
  const statusPresentation = PROVENANCE_STATUS_PRESENTATION[statusKind];
  const glossaryItem = glossary[statusPresentation.glossaryTerm];

  let config = {
    label: statusPresentation.label,
    icon: FileText,
    badgeClass: 'bg-transparent text-slate-400 border-transparent hover:border-slate-700 hover:text-slate-300',
    title: 'Standardized statement data from Screener.in',
    explanation: `${glossaryItem.meaning} ${glossaryItem.howStockerUses || ''} ${glossaryItem.userAction || ''}`.trim()
  };

  if (statusKind === 'discrepancy') {
    config = {
      label: 'Discrepancy',
      icon: AlertTriangle,
      badgeClass: 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border-amber-300 dark:border-amber-800',
      title: 'Discrepancy detected between exchange filing and standardized statements',
      explanation: `${glossaryItem.meaning} ${glossaryItem.howStockerUses || ''} ${glossaryItem.userAction || ''}`.trim()
    };
  } else if (statusKind === 'verified') {
    config = {
      label: 'Verified',
      icon: CheckCircle2,
      badgeClass: 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border-emerald-300 dark:border-emerald-800',
      title: 'Official filing value reconciled with standardized data',
      explanation: `${glossaryItem.meaning} ${glossaryItem.howStockerUses || ''} ${glossaryItem.userAction || ''}`.trim()
    };
  } else if (statusKind === 'mixed') {
    config = {
      label: 'Mixed',
      icon: Layers,
      badgeClass: 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-400 border-blue-300 dark:border-blue-800',
      title: 'Calculated using a combination of verified and standardized inputs',
      explanation: `${glossaryItem.meaning} ${glossaryItem.howStockerUses || ''} ${glossaryItem.userAction || ''}`.trim()
    };
  } else if (statusKind === 'unavailable') {
    config = {
      label: 'Unavailable',
      icon: HelpCircle,
      badgeClass: 'bg-slate-50 dark:bg-slate-900 text-slate-400 border-slate-200 dark:border-slate-800',
      title: 'Required comparable evidence is unavailable',
      explanation: `${glossaryItem.meaning} ${glossaryItem.howStockerUses || ''} ${glossaryItem.userAction || ''}`.trim()
    };
  }

  const Icon = config.icon;
  const showLabel = !(compact && statusPresentation.emphasis === 'low');

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setShowModal(true);
        }}
        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border transition-colors cursor-pointer provenance-${statusPresentation.emphasis} ${config.badgeClass} ${className}`}
        title={config.title}
        aria-label={`${config.label} data provenance. Open source details.`}
        aria-expanded={showModal}
      >
        <Icon className="w-2.5 h-2.5 flex-shrink-0" />
        {showLabel ? <span>{config.label}</span> : <span className="sr-only">{config.label}</span>}
      </button>

      {showModal && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="presentation"
          onClick={(e) => {
            e.stopPropagation();
            setShowModal(false);
          }}
        >
          <div 
            className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg shadow-xl max-w-md w-full p-5 text-left text-xs text-slate-800 dark:text-slate-100"
            role="dialog"
            aria-modal="true"
            aria-label={`${config.label} financial provenance details`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3 mb-3">
              <div className="flex items-center gap-2">
                <Icon className={`w-4 h-4 ${statusKind === 'verified' ? 'text-emerald-500' : statusKind === 'discrepancy' ? 'text-amber-500' : 'text-blue-500'}`} />
                <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Financial Provenance Details</h4>
              </div>
              <button
                ref={closeRef}
                type="button"
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded"
                aria-label="Close financial provenance details"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
              <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
                <span>Input Quality:</span>
                <span className={`font-semibold ${statusKind === 'verified' ? 'text-emerald-600 dark:text-emerald-400' : statusKind === 'discrepancy' ? 'text-amber-600 dark:text-amber-400' : 'text-slate-700 dark:text-slate-300'}`}>
                  {config.label}
                </span>
              </div>
              <p className="text-[11px] leading-relaxed text-slate-600 dark:text-slate-300">{config.explanation}</p>

              {inputs.length > 0 && (
                <div className="space-y-2">
                  <div className="text-[11px] font-medium text-slate-700 dark:text-slate-300">Underlying Datapoints:</div>
                  {inputs.map((inp, idx) => (
                    <div key={idx} className="p-2.5 bg-slate-50 dark:bg-slate-800/60 rounded border border-slate-200 dark:border-slate-700/60 space-y-1">
                      <div className="flex items-center justify-between font-semibold">
                        <span>{inp.period} ({inp.canonical_metric})</span>
                        <span>{formatInputMetricValue(inp.value, inp.unit, inp.currency)}</span>
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400">
                        <span>Source:</span>
                        <span>{inp.selected_source_name || (inp.source_type === 'official' ? 'Official Statutory Filing' : 'Screener.in')}</span>
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400">
                        <span>Status:</span>
                        <span className={`font-medium ${inp.verification_status === 'VERIFIED' ? 'text-emerald-600 dark:text-emerald-400' : inp.verification_status === 'DISCREPANCY' ? 'text-amber-600 dark:text-amber-400' : 'text-slate-600 dark:text-slate-400'}`}>
                          {inp.verification_status}
                        </span>
                      </div>
                      {inp.selected_source_url && (
                        <div className="pt-1">
                          <a 
                            href={inp.selected_source_url} 
                            target="_blank" 
                            rel="noopener noreferrer" 
                            className="inline-flex items-center gap-1 text-[10px] text-blue-600 dark:text-blue-400 hover:underline"
                          >
                            View Filing Document <ExternalLink className="w-2.5 h-2.5" />
                          </a>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-4 pt-3 border-t border-slate-200 dark:border-slate-800 flex justify-end">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="px-3 py-1.5 bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded text-xs font-medium hover:bg-slate-300 dark:hover:bg-slate-700 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
