import React from 'react';
import { Info } from 'lucide-react';
import type { GlossaryTerm } from '../../data/glossary';
import { buildCashFlowAnalysisTable } from '../../utils/cashFlowAnalysis';
import type { CashFlowAnalysisTrend } from '../../utils/cashFlowAnalysis';
import { ConceptHelp } from './ConceptHelp';
import { DataOriginBadge } from './DataOriginBadge';

interface StockerCashFlowAnalysisTableProps {
  trends: CashFlowAnalysisTrend[];
  businessModel?: string;
  sector?: string;
  industry?: string;
  onCalculationDetails?: () => void;
}

const glossaryByMetric: Record<string, GlossaryTerm> = {
  pat: 'pat',
  cfo: 'cfo',
  cfo_pat: 'cfo_pat',
  capex: 'capex',
  fcf: 'fcf'
};

const isFiniteNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);

export const StockerCashFlowAnalysisTable: React.FC<StockerCashFlowAnalysisTableProps> = ({
  trends,
  businessModel,
  sector,
  industry,
  onCalculationDetails
}) => {
  const table = buildCashFlowAnalysisTable(trends);

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        {onCalculationDetails && (
          <button type="button" onClick={onCalculationDetails} className="calculation-link">
            <Info className="w-3.5 h-3.5" aria-hidden="true" />
            Formula &amp; Inputs
          </button>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="cash-analysis-table">
          <thead>
            <tr>
              <th>
                <span>Metric</span>
                <small>₹ Cr unless noted</small>
              </th>
              {table.periods.map(period => <th key={period}>{period}</th>)}
            </tr>
          </thead>
          <tbody>
            {table.rows.map(row => (
              <tr key={row.key}>
                <th scope="row">
                  <span>
                    <ConceptHelp
                      term={glossaryByMetric[row.key]}
                      label={row.label}
                      businessModel={businessModel}
                      sector={sector}
                      industry={industry}
                      onCalculationDetails={row.origin === 'stocker_calculation' ? onCalculationDetails : undefined}
                    />
                    <DataOriginBadge origin={row.origin} compact />
                  </span>
                </th>
                {row.values.map((value, index) => (
                  <td key={`${row.key}-${table.periods[index]}`} className={row.key === 'fcf' && isFiniteNumber(value) && value < 0 ? 'financial-value-negative' : ''}>
                    {isFiniteNumber(value)
                      ? row.unit === 'percent' ? `${value.toLocaleString('en-IN')}%` : value.toLocaleString('en-IN')
                      : '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="cash-methodology-details">
        <summary>Capex input methodology by period</summary>
        <div>
          {table.capexMethodology.map(item => (
            <p key={item.period}><strong>{item.period}:</strong> {item.methodology}</p>
          ))}
        </div>
      </details>
    </div>
  );
};
