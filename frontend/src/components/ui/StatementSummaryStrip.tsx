import React from 'react';
import type { GlossaryTerm } from '../../data/glossary';
import type { TrendTone } from '../../utils/financialMetrics';
import type { AnalyticValueWithProvenance, AnalyticInputProvenance } from '../../types';
import { ConceptHelp } from './ConceptHelp';
import { FinancialProvenanceBadge } from './FinancialProvenanceBadge';

export interface StatementSummaryItem {
  label: string;
  value: React.ReactNode;
  detail?: React.ReactNode;
  tone?: TrendTone;
  concept?: GlossaryTerm;
  onDetails?: () => void;
  provenance?: AnalyticValueWithProvenance | AnalyticInputProvenance | null;
}

interface StatementSummaryStripProps {
  title?: string;
  items: StatementSummaryItem[];
}

export const StatementSummaryStrip: React.FC<StatementSummaryStripProps> = ({ title = 'What changed?', items }) => {
  const visibleItems = items.filter(item => item.value !== null && item.value !== undefined && item.value !== '—');
  if (!visibleItems.length) return null;

  return (
    <section className="statement-summary" aria-label={title}>
      <div className="statement-summary-title">{title}</div>
      <div className="statement-summary-grid">
        {visibleItems.map(item => (
          <div key={item.label} className={`statement-summary-item summary-${item.tone || 'neutral'}`}>
            <div className="flex items-center justify-between gap-1">
              <span className="statement-summary-label">
                {item.concept ? <ConceptHelp term={item.concept} label={item.label} onCalculationDetails={item.onDetails} /> : item.label}
              </span>
              {item.provenance && <FinancialProvenanceBadge provenance={item.provenance} compact />}
            </div>
            <strong className="statement-summary-value">{item.value}</strong>
            {item.detail && <span className="statement-summary-detail">{item.detail}</span>}
          </div>
        ))}
      </div>
    </section>
  );
};

