export interface CashFlowAnalysisTrend {
  period: string;
  reported_pat_cr: number | null;
  reported_cfo_cr: number | null;
  cfo_to_pat_pct: number | null;
  capex_cr: number | null;
  stocker_derived_fcf_cr: number | null;
  capex_methodology?: string | null;
}

export type CashFlowAnalysisMetricKey = 'pat' | 'cfo' | 'cfo_pat' | 'capex' | 'fcf';

export interface CashFlowAnalysisMetricRow {
  key: CashFlowAnalysisMetricKey;
  label: string;
  unit: 'crores' | 'percent';
  origin: 'reported_fact' | 'reported_or_derived' | 'stocker_calculation';
  values: Array<number | null>;
}

export interface CashFlowAnalysisTableModel {
  periods: string[];
  rows: CashFlowAnalysisMetricRow[];
  capexMethodology: Array<{ period: string; methodology: string }>;
}

export const buildCashFlowAnalysisTable = (trends: CashFlowAnalysisTrend[]): CashFlowAnalysisTableModel => ({
  periods: trends.map(trend => trend.period),
  rows: [
    { key: 'pat', label: 'PAT', unit: 'crores', origin: 'reported_fact', values: trends.map(trend => trend.reported_pat_cr) },
    { key: 'cfo', label: 'CFO', unit: 'crores', origin: 'reported_fact', values: trends.map(trend => trend.reported_cfo_cr) },
    { key: 'cfo_pat', label: 'CFO / PAT', unit: 'percent', origin: 'stocker_calculation', values: trends.map(trend => trend.cfo_to_pat_pct) },
    { key: 'capex', label: 'Capex input', unit: 'crores', origin: 'reported_or_derived', values: trends.map(trend => trend.capex_cr) },
    { key: 'fcf', label: 'FCF', unit: 'crores', origin: 'stocker_calculation', values: trends.map(trend => trend.stocker_derived_fcf_cr) }
  ],
  capexMethodology: trends.map(trend => ({
    period: trend.period,
    methodology: trend.capex_methodology || 'Method not supplied'
  }))
});
