import React from 'react';
import type { FinancialStatement } from '../../types';
import type { GlossaryTerm } from '../../data/glossary';
import { getMetricPresentation, isGenuinelyNegativeResult } from '../../utils/financialMetrics';
import { ConceptHelp } from './ConceptHelp';
import { FinancialMetricCell, trendToneFromValues } from './TrendValue';
import { Sparkline } from './Sparkline';

const getStatementGlossaryTerm = (metric: string): GlossaryTerm | null => {
  const normalized = metric.toLowerCase();
  if (normalized.includes('operating profit margin') || normalized === 'opm %') return 'opm';
  if (normalized.includes('ebitda') || normalized === 'operating profit') return 'ebitda';
  if (normalized.includes('cash from operating') || normalized.includes('operating cash flow')) return 'cfo';
  if (normalized.includes('free cash flow')) return 'fcf';
  if (normalized.includes('receivable') || normalized.includes('debtor')) return 'receivables';
  if (normalized.includes('inventory')) return 'inventory';
  if (normalized.includes('capital work in progress') || normalized.includes('cwip')) return 'cwip';
  if (normalized.includes('working capital')) return 'working_capital';
  return null;
};

interface FinancialStatementTableProps {
  statement: FinancialStatement;
  comparisonLabel?: string;
}

export const FinancialStatementTable: React.FC<FinancialStatementTableProps> = ({ statement, comparisonLabel = 'vs prior period' }) => {
  const latestIndex = statement.periods.length - 1;

  return (
    <div className="financial-table-wrap">
      <table className="financial-table">
        <thead>
          <tr>
            <th className="financial-metric-heading">
              <span>Metric</span>
              <small>₹ Cr unless noted</small>
            </th>
            {statement.periods.map((period, index) => (
              <th key={period} className={`${index % 2 ? 'statement-col-band' : ''} ${index === latestIndex ? 'statement-latest-col' : ''}`}>
                <span>{period}</span>
                {index === latestIndex && <small className="latest-label">Latest</small>}
              </th>
            ))}
            <th className="financial-trend-heading">
              <span>Trend</span>
              <small>{comparisonLabel}</small>
            </th>
          </tr>
        </thead>
        <tbody>
          {statement.rows.map((row, rowIndex) => {
            const presentation = getMetricPresentation(row.metric);
            const glossaryTerm = getStatementGlossaryTerm(row.metric);
            const values = statement.periods.map(period => row.values[period]);
            const latestValue = values[latestIndex];
            const previousValue = values[latestIndex - 1];
            const latestTone = isGenuinelyNegativeResult(row.metric, latestValue)
              ? 'negative'
              : trendToneFromValues(row.metric, latestValue, previousValue);
            const rowClass = presentation.importance === 'core'
              ? 'financial-row-core'
              : presentation.importance === 'supporting' ? 'financial-row-supporting' : '';

            return (
              <tr key={`${row.metric}-${rowIndex}`} className={rowClass}>
                <td className="financial-metric-name">
                  <span>{row.metric}{glossaryTerm && <ConceptHelp term={glossaryTerm} />}</span>
                </td>
                {statement.periods.map((period, periodIndex) => (
                  <td key={period} className={`${periodIndex % 2 ? 'statement-col-band' : ''} ${periodIndex === latestIndex ? `statement-latest-col statement-latest-${latestTone}` : ''}`}>
                    <FinancialMetricCell
                      metric={row.metric}
                      value={row.values[period]}
                      previous={periodIndex > 0 ? row.values[statement.periods[periodIndex - 1]] : null}
                      showChange={periodIndex === latestIndex && presentation.direction !== 'neutral'}
                    />
                  </td>
                ))}
                <td className="financial-sparkline-cell">
                  {presentation.showSparkline
                    ? <Sparkline values={values} label={`${row.metric} trend`} tone={trendToneFromValues(row.metric, latestValue, previousValue)} />
                    : <span className="sparkline-empty" aria-hidden="true">—</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
