import React from 'react';
import type { ComparisonStanding } from '../../utils/financialMetrics';

interface ComparisonHighlightProps {
  standing: ComparisonStanding;
  children: React.ReactNode;
}

export const ComparisonHighlight: React.FC<ComparisonHighlightProps> = ({ standing, children }) => (
  <div className={`comparison-highlight comparison-${standing}`}>
    <span>{children}</span>
    {standing === 'best' && <small><span aria-hidden="true">★</span> Best</small>}
    {standing === 'weakest' && <small><span aria-hidden="true">↓</span> Weakest</small>}
  </div>
);
