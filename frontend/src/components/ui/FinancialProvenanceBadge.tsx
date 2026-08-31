import React, { useState } from 'react';
import { CheckCircle2, FileText, Layers, AlertTriangle, HelpCircle, ExternalLink, X } from 'lucide-react';
import type { AnalyticValueWithProvenance, AnalyticInputProvenance } from '../../types';

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

  let config = {
    label: 'Standardized',
    icon: FileText,
    badgeClass: 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700',
    title: 'Standardized statement data from Screener.in'
  };

  if (quality === 'discrepant' || hasDiscrepancy) {
    config = {
      label: 'Discrepancy',
      icon: AlertTriangle,
      badgeClass: 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border-amber-300 dark:border-amber-800',
      title: 'Discrepancy detected between exchange filing and reported statements'
    };
  } else if (quality === 'verified') {
    config = {
      label: 'Verified',
      icon: CheckCircle2,
      badgeClass: 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border-emerald-300 dark:border-emerald-800',
      title: 'Officially verified against statutory exchange filing'
    };
  } else if (quality === 'mixed') {
    config = {
      label: 'Mixed',
      icon: Layers,
      badgeClass: 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-400 border-blue-300 dark:border-blue-800',
      title: 'Calculated using combination of verified and standardized inputs'
    };
  } else if (quality === 'insufficient') {
    config = {
      label: 'Unavailable',
      icon: HelpCircle,
      badgeClass: 'bg-slate-50 dark:bg-slate-900 text-slate-400 border-slate-200 dark:border-slate-800',
      title: 'Required historical counterpart missing or unverified'
    };
  }

  const Icon = config.icon;

  return (
    <>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setShowModal(true);
        }}
        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border transition-colors hover:opacity-80 cursor-pointer ${config.badgeClass} ${className}`}
        title={config.title}
      >
        <Icon className="w-2.5 h-2.5 flex-shrink-0" />
        <span>{config.label}</span>
      </button>

      {showModal && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={(e) => {
            e.stopPropagation();
            setShowModal(false);
          }}
        >
          <div 
            className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg shadow-xl max-w-md w-full p-5 text-left text-xs text-slate-800 dark:text-slate-100"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3 mb-3">
              <div className="flex items-center gap-2">
                <Icon className={`w-4 h-4 ${quality === 'verified' ? 'text-emerald-500' : quality === 'discrepant' ? 'text-amber-500' : 'text-blue-500'}`} />
                <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Financial Provenance Details</h4>
              </div>
              <button 
                type="button"
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
              <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
                <span>Input Quality:</span>
                <span className={`font-semibold capitalize ${quality === 'verified' ? 'text-emerald-600 dark:text-emerald-400' : quality === 'discrepant' ? 'text-amber-600 dark:text-amber-400' : 'text-slate-700 dark:text-slate-300'}`}>
                  {quality}
                </span>
              </div>

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

