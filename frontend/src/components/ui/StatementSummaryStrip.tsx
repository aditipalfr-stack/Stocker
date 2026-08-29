import React from 'react';
import type { GlossaryTerm } from '../../data/glossary';
import type { TrendTone } from '../../utils/financialMetrics';
import { ConceptHelp } from './ConceptHelp';

export interface StatementSummaryItem {
  label: string;
  value: React.ReactNode;
  detail?: React.ReactNode;
  tone?: TrendTone;
  concept?: GlossaryTerm;
  onDetails?: () => void;
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
            <span className="statement-summary-label">
              {item.concept ? <ConceptHelp term={item.concept} label={item.label} onCalculationDetails={item.onDetails} /> : item.label}
            </span>
            <strong className="statement-summary-value">{item.value}</strong>
            {item.detail && <span className="statement-summary-detail">{item.detail}</span>}
          </div>
        ))}
      </div>
    </section>
  );
};
