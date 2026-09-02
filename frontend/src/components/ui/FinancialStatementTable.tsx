import React from 'react';
import type { FinancialStatement } from '../../types';
import { getStatementGlossaryTerm } from '../../data/statementGlossary';
import {
  calculatePeriodChange,
  getMetricPresentation,
  parseFinancialPeriod,
  selectStatementPeriods
} from '../../utils/financialMetrics';
import type { FinancialStatementKind } from '../../utils/financialMetrics';
import { ConceptHelp } from './ConceptHelp';
import { ChangeIndicator, FinancialMetricCell, trendToneFromValues } from './TrendValue';
import { Sparkline } from './Sparkline';

interface FinancialStatementTableProps {
  statement: FinancialStatement;
  statementKind: FinancialStatementKind;
  businessModel?: string;
  sector?: string;
  industry?: string;
}

const latestLabelFor = (statementKind: FinancialStatementKind) => {
  if (statementKind === 'quarterly') return 'Latest quarter';
  if (statementKind === 'balance_sheet') return 'Latest balance';
  return 'Latest FY';
};

export const FinancialStatementTable: React.FC<FinancialStatementTableProps> = ({ statement, statementKind, businessModel, sector, industry }) => {
  const selection = selectStatementPeriods(statement.periods, statementKind);

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
              const isTTM = parseFinancialPeriod(period, statementKind).kind === 'ttm';
              const isComparisonCurrent = index === selection.currentIndex;
              return (
                <th key={period} className={`${index % 2 ? 'statement-col-band' : ''} ${isComparisonCurrent ? 'statement-latest-col' : ''} ${isTTM ? 'statement-ttm-col' : ''}`}>
                  <span>{period}{isTTM && <ConceptHelp term="ttm" businessModel={businessModel} />}</span>
                  {isComparisonCurrent && <small className="latest-label">{latestLabelFor(statementKind)}</small>}
                  {isComparisonCurrent && <small className="latest-comparison-label">{selection.comparisonLabel}</small>}
                  {isTTM && <small className="ttm-label">Separate · no FY comparison</small>}
                </th>
              );
            })}
            <th className="financial-trend-heading">
              <span>Change / Trend</span>
              <small>{selection.comparisonBasisLabel} · historical shape</small>
            </th>
          </tr>
        </thead>
        <tbody>
          {statement.rows.map((row, rowIndex) => {
            const presentation = getMetricPresentation(row.metric, businessModel);
            const glossaryTerm = getStatementGlossaryTerm(row.metric);
            const values = statement.periods.map(period => row.values[period]);
            const currentValue = selection.currentIndex === null ? null : values[selection.currentIndex];
            const previousValue = selection.previousIndex === null ? null : values[selection.previousIndex];
            const historyValues = selection.historyIndices.map(index => values[index]);
            const validHistoryCount = historyValues.filter(value => typeof value === 'number' && Number.isFinite(value)).length;
            const hasExactChange = calculatePeriodChange(row.metric, currentValue, previousValue, businessModel) !== null;
            const rowClass = presentation.importance === 'core'
              ? 'financial-row-core'
              : presentation.importance === 'supporting' ? 'financial-row-supporting' : '';

            return (
              <tr key={`${row.metric}-${rowIndex}`} className={rowClass}>
                <td className="financial-metric-name">
                  <span>{glossaryTerm ? <ConceptHelp term={glossaryTerm} label={row.metric} businessModel={businessModel} sector={sector} industry={industry} /> : row.metric}</span>
                </td>
                {statement.periods.map((period, periodIndex) => {
                  const isCellTTM = parseFinancialPeriod(period, statementKind).kind === 'ttm';
                  const isComparisonCurrent = periodIndex === selection.currentIndex;
                  return (
                    <td key={period} className={`${periodIndex % 2 ? 'statement-col-band' : ''} ${isComparisonCurrent ? 'statement-latest-col' : ''} ${isCellTTM ? 'statement-ttm-col' : ''}`}>
                      <FinancialMetricCell
                        metric={row.metric}
                        value={row.values[period]}
                        businessModel={businessModel}
                      />
                    </td>
                  );
                })}
                <td className="financial-sparkline-cell">
                  <div className="change-trend-stack">
                    {hasExactChange ? (
                      <ChangeIndicator
                        metric={row.metric}
                        current={currentValue}
                        previous={previousValue}
                        currentPeriod={selection.currentPeriod}
                        previousPeriod={selection.previousPeriod}
                        comparisonLabel={selection.comparisonLabel}
                        visibleComparisonLabel={selection.comparisonBasisLabel}
                        className="change-trend-indicator"
                        businessModel={businessModel}
                      />
                    ) : (
                      <span className="change-unavailable">No exact comparison</span>
                    )}
                    {validHistoryCount >= 2 ? (
                      <Sparkline
                        values={historyValues}
                        label={`${row.metric} historical shape (${selection.historyLabel}${statementKind === 'quarterly' ? '' : '; TTM excluded'})`}
                        tone={trendToneFromValues(row.metric, currentValue, previousValue, businessModel)}
                      />
                    ) : <span className="sparkline-empty" aria-label={`${row.metric} history: not enough comparable data`}>—</span>}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
