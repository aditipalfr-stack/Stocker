import React, { useEffect } from 'react';
import { Calculator, X } from 'lucide-react';
import { FormulaTransparencyItem } from '../../types';
import { DataOriginBadge } from './DataOriginBadge';

interface FormulaTransparencyModalProps {
  item: FormulaTransparencyItem | null;
  onClose: () => void;
}

export const FormulaTransparencyModal: React.FC<FormulaTransparencyModalProps> = ({ item, onClose }) => {
  useEffect(() => {
    if (!item) return;
    const closeOnEscape = (event: KeyboardEvent) => event.key === 'Escape' && onClose();
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [item, onClose]);

  if (!item) return null;

  const suffix = item.metric_name.includes('%') || item.metric_name.includes('CAGR') ? '%' : '';

  return (
    <div className="modal-backdrop items-center justify-center p-4" role="presentation" onMouseDown={onClose}>
      <div className="theme-modal max-w-lg w-full space-y-5" role="dialog" aria-modal="true" aria-labelledby="formula-title" onMouseDown={(event) => event.stopPropagation()}>
        <div className="flex items-start justify-between gap-3 border-b border-theme pb-4">
          <div className="flex items-center gap-3">
            <div className="feature-icon feature-icon-cyan"><Calculator className="w-5 h-5" /></div>
            <div>
              <h4 id="formula-title" className="text-base font-bold text-primary">{item.metric_name}</h4>
              <DataOriginBadge origin="stocker_calculation" className="mt-1" />
            </div>
          </div>
          <button type="button" onClick={onClose} className="icon-button" aria-label="Close calculation details"><X className="w-4 h-4" /></button>
        </div>

        <div className="space-y-4 text-xs">
          <div className="detail-block flex items-center justify-between gap-4">
            <span className="help-eyebrow">Calculated output</span>
            <span className="text-xl font-extrabold text-positive font-mono">
              {typeof item.value === 'number'
                ? Number.isFinite(item.value) ? `${item.value.toLocaleString('en-IN')}${suffix}` : 'N/A'
                : item.value !== null && item.value !== undefined ? String(item.value) : 'N/A'}
            </span>
          </div>

          <div className="detail-block space-y-1.5">
            <span className="help-eyebrow">Formula used</span>
            <code className="formula-chip">{item.formula}</code>
          </div>

          <div className="detail-block space-y-2">
            <span className="help-eyebrow">Exact inputs from statements</span>
            <div className="space-y-1.5 font-mono text-[11px]">
              {Object.entries(item.inputs).map(([key, value]) => (
                <div key={key} className="flex items-center justify-between gap-4 py-1 border-b border-theme last:border-0">
                  <span className="text-secondary">{key}:</span>
                  <span className="text-primary font-bold text-right">
                    {typeof value === 'number'
                      ? Number.isFinite(value) ? value.toLocaleString('en-IN') : 'N/A'
                      : value !== null && value !== undefined ? String(value) : 'N/A'}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="detail-block space-y-1.5">
            <span className="help-eyebrow">This Stocker calculation</span>
            <p className="text-secondary leading-relaxed">{item.explanation}</p>
            <span className="text-[10px] text-muted font-mono block pt-1">Source: {item.source}</span>
          </div>
        </div>

        <div className="pt-1 text-right">
          <button type="button" onClick={onClose} className="secondary-button">Close</button>
        </div>
      </div>
    </div>
  );
};
