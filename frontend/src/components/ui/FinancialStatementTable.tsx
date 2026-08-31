import React from 'react';
import type { FinancialStatement } from '../../types';
import type { GlossaryTerm } from '../../data/glossary';
import { getMetricPresentation, isGenuinelyNegativeResult } from '../../utils/financialMetrics';
import { ConceptHelp } from './ConceptHelp';
import { FinancialMetricCell, trendToneFromValues } from './TrendValue';
import { Sparkline } from './Sparkline';

const getStatementGlossaryTerm = (metric: string): GlossaryTerm | null => {
  const normalized = metric.trim().toLowerCase().replace(/\s+/g, ' ');
  if (['sales', 'revenue', 'revenue from operations', 'total income'].includes(normalized)) return 'revenue';
  if (['net profit', 'pat', 'profit after tax', 'net income'].includes(normalized)) return 'pat';
  if (normalized.includes('operating profit margin') || normalized === 'opm %') return 'opm';
  if (normalized === 'operating profit') return 'operating_profit';
  if (normalized === 'ebitda') return 'ebitda';
  if (['eps in rs', 'eps', 'basic eps', 'diluted eps'].includes(normalized)) return 'eps';
  if (normalized.includes('cash from operating') || normalized.includes('operating cash flow')) return 'cfo';
  if (normalized.includes('free cash flow')) return 'fcf';
  if (['capital expenditure', 'capex'].includes(normalized)) return 'capex';
  if (['borrowings', 'total borrowings', 'debt'].includes(normalized)) return 'borrowings';
  if (['fixed assets', 'net fixed assets'].includes(normalized)) return 'fixed_assets';
  if (['net block'].includes(normalized)) return 'net_block';
  if (['deposits', 'total deposits'].includes(normalized)) return 'deposits';
  if (['advances', 'loans & advances', 'loans and advances', 'total advances'].includes(normalized)) return 'advances';
  if (['gross npa', 'gross npa %', 'gnpa', 'gnpa %'].includes(normalized)) return 'gnpa';
  if (['net npa', 'net npa %', 'nnpa', 'nnpa %'].includes(normalized)) return 'nnpa';
  if (normalized.includes('receivable') || normalized.includes('debtor')) return 'receivables';
  if (normalized.includes('inventory')) return 'inventory';
  if (normalized.includes('capital work in progress') || normalized.includes('cwip')) return 'cwip';
  if (normalized.includes('working capital')) return 'working_capital';
  return null;
};

interface FinancialStatementTableProps {
  statement: FinancialStatement;
  comparisonLabel?: string;
  businessModel?: string;
}

export const FinancialStatementTable: React.FC<FinancialStatementTableProps> = ({ statement, comparisonLabel, businessModel }) => {
  const latestIndex = statement.periods.length - 1;
  const latestPeriod = statement.periods[latestIndex] || '';
  const isLatestTTM = latestPeriod.trim().toUpperCase() === 'TTM';
  const resolvedComparisonLabel = comparisonLabel || (isLatestTTM ? 'vs last completed FY' : 'vs prior period');

  return (
    <div className="financial-table-wrap">
      <table className="financial-table">
        <thead>
          <tr>
            <th className="financial-metric-heading">
              <span>Metric</span>
              <small>₹ Cr unless noted</small>
            </th>
            {statement.periods.map((period, index) => {
              const isTTM = period.trim().toUpperCase() === 'TTM';
              return (
                <th key={period} className={`${index % 2 ? 'statement-col-band' : ''} ${index === latestIndex ? 'statement-latest-col' : ''}`}>
                  <span>{period}{isTTM && <ConceptHelp term="ttm" businessModel={businessModel} />}</span>
                  {index === latestIndex && (
                    <small className="latest-label">{isTTM ? 'TTM' : 'Latest'}</small>
                  )}
                </th>
              );
            })}
            <th className="financial-trend-heading">
              <span>Trend</span>
              <small>{resolvedComparisonLabel}</small>
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
                  <span>{row.metric}{glossaryTerm && <ConceptHelp term={glossaryTerm} businessModel={businessModel} />}</span>
                </td>
                {statement.periods.map((period, periodIndex) => {
                  const isCellTTM = period.trim().toUpperCase() === 'TTM';
                  return (
                    <td key={period} className={`${periodIndex % 2 ? 'statement-col-band' : ''} ${periodIndex === latestIndex ? `statement-latest-col statement-latest-${isLatestTTM ? 'neutral' : latestTone}` : ''}`}>
                      <FinancialMetricCell
                        metric={row.metric}
                        value={row.values[period]}
                        previous={periodIndex > 0 ? row.values[statement.periods[periodIndex - 1]] : null}
                        showChange={periodIndex === latestIndex && presentation.direction !== 'neutral' && !isCellTTM}
                      />
                    </td>
                  );
                })}
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
