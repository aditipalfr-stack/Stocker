import React from 'react';
import { HelpCircle } from 'lucide-react';

export const FinancialColorLegend: React.FC = () => (
  <details className="financial-legend">
    <summary>
      <HelpCircle className="w-3.5 h-3.5" />
      How to read this table
    </summary>
    <div className="financial-legend-popover">
      <p><span className="legend-mark legend-positive">↑</span><strong>Green</strong> — financially positive improvement.</p>
      <p><span className="legend-mark legend-negative">↓</span><strong>Red</strong> — deterioration or a negative financial result.</p>
      <p><span className="legend-mark legend-warning">!</span><strong>Amber</strong> — caution or an existing risk signal.</p>
      <p><span className="legend-mark legend-neutral">↕</span><strong>Neutral</strong> — direction alone is not enough to judge.</p>
      <small>Colors explain the observed change; they are not investment advice.</small>
    </div>
  </details>
);
