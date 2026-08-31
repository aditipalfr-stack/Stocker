import { BusinessAnalysisView } from './business_analysis/BusinessAnalysisView';
import React, { useState, useEffect } from 'react';
import { 
  StockDetail, ProjectionAssumption, ProjectionResult, 
  FinancialStatement, BusinessAnalysisIntelligence, ResearchLifecycleStatus
} from '../types';
import { 
  projectStock, fetchBusinessAnalysis, generateDocIntelligence,
  fetchAiStatus, configureAiKey, AiStatusResult, fetchStockDetail
} from '../api';
import { 
  TrendingUp, BarChart3, Sliders, FileText, ShieldAlert, 
  ExternalLink, ArrowUpRight, ArrowDownRight, RefreshCw, 
  CheckCircle2, AlertTriangle, Sparkles, Building, Layers, 
  DollarSign, Activity, FileSpreadsheet, ChevronRight, HelpCircle,
  Clock, Target, Compass, Search, Zap, Info, ChevronDown,
  Mic, Presentation, Bell, KeyRound, Check, Calculator
} from 'lucide-react';
import { 
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, 
  Tooltip, CartesianGrid, BarChart, Bar, Legend, LineChart, Line,
  Cell, ReferenceLine
} from 'recharts';
import { ConceptHelp } from './ui/ConceptHelp';
import { DataOriginBadge } from './ui/DataOriginBadge';
import { FormulaTransparencyModal } from './ui/FormulaTransparencyModal';
import { FinancialStatementTable } from './ui/FinancialStatementTable';
import { FinancialColorLegend } from './ui/FinancialColorLegend';
import { StatementSummaryStrip } from './ui/StatementSummaryStrip';
import type { StatementSummaryItem } from './ui/StatementSummaryStrip';
import { ChangeIndicator, ExplicitChangeIndicator } from './ui/TrendValue';
import type { TrendTone } from '../utils/financialMetrics';
import { BackgroundResearchState, ResearchStatusPanel } from './ResearchStatusPanel';

interface StockDetailViewProps {
  stock: StockDetail;
  onBack: () => void;
  onScrapeRefresh?: () => void | Promise<void>;
  isFinancialRefreshing?: boolean;
  researchStatus: ResearchLifecycleStatus | null;
  researchStatusLoading?: boolean;
  researchStatusError?: string | null;
  filingDiscoveryState?: BackgroundResearchState;
  filingDiscoveryRevision: number;
  verificationState?: BackgroundResearchState;
  onRetryFilings?: () => void;
  onRetryVerification?: () => void;
  onRefreshResearchStatus?: () => Promise<void>;
  onStockUpdated: (stock: StockDetail) => void;
}

const findStatementRow = (statement: FinancialStatement, aliases: string[]) => statement.rows.find(row => {
  const normalized = row.metric.trim().toLowerCase();
  return aliases.some(alias => normalized === alias || (alias.length > 3 && normalized.includes(alias)));
});

const latestRowPair = (statement: FinancialStatement, aliases: string[]) => {
  const row = findStatementRow(statement, aliases);
  const latestPeriod = statement.periods[statement.periods.length - 1];
  const previousPeriod = statement.periods[statement.periods.length - 2];
  return {
    metric: row?.metric || aliases[0],
    current: latestPeriod ? row?.values[latestPeriod] ?? null : null,
    previous: previousPeriod ? row?.values[previousPeriod] ?? null : null
  };
};

const isFiniteNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const formatCrores = (value: number | null | undefined) => isFiniteNumber(value) ? `₹${value.toLocaleString('en-IN')} Cr` : '—';
const formatRupees = (value: number | null | undefined) => isFiniteNumber(value) ? `₹${value.toLocaleString('en-IN')}` : '—';
const formatPercent = (value: number | null | undefined) => isFiniteNumber(value) ? `${value.toLocaleString('en-IN')}%` : '—';
const formatMultiple = (value: number | null | undefined) => isFiniteNumber(value) ? `${value.toLocaleString('en-IN')}x` : '—';
const formatCompactCrores = (value: number) => isFiniteNumber(value) ? `₹${Intl.NumberFormat('en-IN', { notation: 'compact', maximumFractionDigits: 1 }).format(value)}` : '—';
const formatIndianNumber = (value: number | null | undefined) => isFiniteNumber(value) ? value.toLocaleString('en-IN') : '—';
const guidanceRunRateUsesPercent = (metricName: string) => {
  const metric = metricName.toLowerCase();
  const isOperational = ['capacity', 'order', 'arpu', 'subscriber', 'user', 'store', 'outlet', 'volume', 'tcv', 'deal']
    .some(keyword => metric.includes(keyword));
  return !isOperational && ['revenue', 'sales', 'margin', 'growth', 'pat', 'profit']
    .some(keyword => metric.includes(keyword));
};
const toneFromSignedValue = (value: number | null | undefined): TrendTone => !isFiniteNumber(value) || value === 0 ? 'neutral' : value > 0 ? 'positive' : 'negative';
const toneForPositiveMetric = (current: number | null | undefined, previous: number | null | undefined): TrendTone => {
  if (current === null || current === undefined) return 'neutral';
  if (current < 0) return 'negative';
  if (previous === null || previous === undefined) return 'neutral';
  return toneFromSignedValue(current - previous);
};
const cashConversionTone = (quality: string | null | undefined): TrendTone => {
  const normalized = quality?.toLowerCase() || '';
  if (normalized.includes('superior') || normalized.includes('adequate')) return 'positive';
  if (normalized.includes('moderate') || normalized.includes('weak')) return 'warning';
  return 'neutral';
};

export const StockDetailView: React.FC<StockDetailViewProps> = ({
  stock, onBack, onScrapeRefresh, isFinancialRefreshing, researchStatus,
  researchStatusLoading, researchStatusError, filingDiscoveryState,
  filingDiscoveryRevision, verificationState, onRetryFilings, onRetryVerification,
  onRefreshResearchStatus, onStockUpdated
}) => {
  const [activeTab, setActiveTab] = useState<'financials' | 'charts' | 'projection' | 'outlook' | 'scorecard'>('projection');
  const [financialSubTab, setFinancialSubTab] = useState<'quarters' | 'pl' | 'balance_sheet' | 'cash_flow'>('quarters');
  
  // Business Analysis State
  const [docIntel, setDocIntel] = useState<BusinessAnalysisIntelligence | null>(null);
  const [loadingDocIntel, setLoadingDocIntel] = useState<boolean>(false);
  const [generatingDocIntel, setGeneratingDocIntel] = useState<boolean>(false);
  const [docIntelError, setDocIntelError] = useState<string | null>(null);
  const [selectedFormulaKey, setSelectedFormulaKey] = useState<string | null>(null);

  // AI Configuration & Progress State
  const [aiStatus, setAiStatus] = useState<AiStatusResult | null>(null);
  const [isKeyModalOpen, setIsKeyModalOpen] = useState<boolean>(false);
  const [inputKey, setInputKey] = useState<string>('');
  const [savingKey, setSavingKey] = useState<boolean>(false);
  const [keySaveMessage, setKeySaveMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [generationStep, setGenerationStep] = useState<number>(0);

  // Projection Simulator State
  const [growthRate, setGrowthRate] = useState<number>(stock.projection.assumptions.revenue_growth_rate_pct);
  const [opmRate, setOpmRate] = useState<number>(stock.projection.assumptions.target_opm_pct);
  const [capexRate, setCapexRate] = useState<number>(stock.projection.assumptions.capex_pct_of_sales);
  const [exitPe, setExitPe] = useState<number>(stock.projection.assumptions.target_exit_pe);
  const [wacc, setWacc] = useState<number>(stock.projection.assumptions.discount_rate_wacc_pct);
  const [terminalG, setTerminalG] = useState<number>(stock.projection.assumptions.terminal_growth_rate_pct);
  
  const [projectionResult, setProjectionResult] = useState<ProjectionResult>(stock.projection);
  const [isProjecting, setIsProjecting] = useState<boolean>(false);

  // Load business analysis and check AI status on mount / stock change
  useEffect(() => {
    fetchAiStatus().then(setAiStatus).catch(() => {});
    
    const loadIntel = async () => {
      setLoadingDocIntel(true);
      setDocIntelError(null);
      try {
        const intel = await fetchBusinessAnalysis(stock.symbol);
        setDocIntel(intel);
      } catch (err: any) {
        setDocIntelError(err.message || 'Failed to load business analysis');
      } finally {
        setLoadingDocIntel(false);
      }
    };
    loadIntel();
  }, [stock.symbol]);

  const handleGenerateIntel = async () => {
    // Check AI connection status first
    try {
      const status = await fetchAiStatus();
      setAiStatus(status);
      if (!status.configured || status.status === 'missing_key') {
        setIsKeyModalOpen(true);
        return;
      }
      if (status.status === 'network_error' || status.status === 'quota_exceeded') {
        setDocIntelError(status.message);
        return;
      }
      if (status.status === 'invalid_key') {
        setDocIntelError(status.message);
        setIsKeyModalOpen(true);
        return;
      }
    } catch (e) {
      // Proceed
    }

    setGeneratingDocIntel(true);
    setDocIntelError(null);
    setGenerationStep(1);

    const stepTimer1 = setTimeout(() => setGenerationStep(2), 2500);
    const stepTimer2 = setTimeout(() => setGenerationStep(3), 6000);

    try {
      const res = await generateDocIntelligence(stock.symbol);
      setGenerationStep(4);
      setDocIntel(res);
      try {
        const updatedStock = await fetchStockDetail(stock.symbol);
        onStockUpdated(updatedStock);
      } catch (refreshError: any) {
        setDocIntelError(`Business analysis completed, but dependent projection and score data could not be refreshed: ${refreshError.message || 'refresh failed'}`);
      }
      if (onRefreshResearchStatus) void onRefreshResearchStatus().catch(() => {});
    } catch (err: any) {
      setDocIntelError(err.message || 'Failed to run AI document extraction. Please check your Gemini API key in .env.');
    } finally {
      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);
      setGeneratingDocIntel(false);
    }
  };

  const handleSaveKey = async () => {
    if (!inputKey.trim()) {
      setKeySaveMessage({ type: 'error', text: 'Please enter a valid Gemini API key.' });
      return;
    }
    setSavingKey(true);
    setKeySaveMessage(null);
    try {
      const res = await configureAiKey(inputKey.trim(), 'gemini');
      setAiStatus(res);
      if (res.status === 'active') {
        setKeySaveMessage({ type: 'success', text: '✓ Gemini API key verified and operational!' });
        setTimeout(() => {
          setIsKeyModalOpen(false);
          setKeySaveMessage(null);
          setInputKey('');
        }, 1200);
      } else {
        setKeySaveMessage({ type: 'error', text: res.message });
      }
    } catch (err: any) {
      setKeySaveMessage({ type: 'error', text: err.message || 'Failed to connect to Gemini API.' });
    } finally {
      setSavingKey(false);
    }
  };

  // Sync state when stock prop changes
  useEffect(() => {
    setGrowthRate(stock.projection.assumptions.revenue_growth_rate_pct);
    setOpmRate(stock.projection.assumptions.target_opm_pct);
    setCapexRate(stock.projection.assumptions.capex_pct_of_sales);
    setExitPe(stock.projection.assumptions.target_exit_pe);
    setWacc(stock.projection.assumptions.discount_rate_wacc_pct);
    setTerminalG(stock.projection.assumptions.terminal_growth_rate_pct);
    setProjectionResult(stock.projection);
  }, [stock]);

  // Recalculate projections
  const handleRunProjection = async (customAssumptions?: Partial<ProjectionAssumption>, scenarioName = "Custom") => {
    setIsProjecting(true);
    try {
      const assumptions: ProjectionAssumption = {
        revenue_growth_rate_pct: customAssumptions?.revenue_growth_rate_pct ?? growthRate,
        target_opm_pct: customAssumptions?.target_opm_pct ?? opmRate,
        capex_pct_of_sales: customAssumptions?.capex_pct_of_sales ?? capexRate,
        target_exit_pe: customAssumptions?.target_exit_pe ?? exitPe,
        discount_rate_wacc_pct: customAssumptions?.discount_rate_wacc_pct ?? wacc,
        terminal_growth_rate_pct: customAssumptions?.terminal_growth_rate_pct ?? terminalG,
        effective_tax_rate_pct: 25.0
      };
      const res = await projectStock(stock.symbol, assumptions);
      res.scenario_type = scenarioName;
      setProjectionResult(res);
    } catch (e) {
      console.error(e);
    } finally {
      setIsProjecting(false);
    }
  };

  const applyPreset = (type: 'bull' | 'base' | 'bear') => {
    const baseGrowth = stock.projection.historical_revenue_cagr_3yr;
    const baseOpm = stock.projection.historical_opm_median;
    const pe = stock.ratios.stock_pe;
    if (!isFiniteNumber(baseGrowth) || !isFiniteNumber(baseOpm) || !isFiniteNumber(pe)) return;

    if (type === 'bull') {
      const g = Math.round((baseGrowth * 1.3) * 10) / 10;
      const opm = Math.round((baseOpm + 2.0) * 10) / 10;
      const exit = Math.round(pe * 1.15 * 10) / 10;
      setGrowthRate(g);
      setOpmRate(opm);
      setExitPe(exit);
      handleRunProjection({ revenue_growth_rate_pct: g, target_opm_pct: opm, target_exit_pe: exit }, "Bull Case (+30% Momentum)");
    } else if (type === 'bear') {
      const g = Math.round((baseGrowth * 0.7) * 10) / 10;
      const opm = Math.round((baseOpm - 2.5) * 10) / 10;
      const exit = Math.round(pe * 0.8 * 10) / 10;
      setGrowthRate(g);
      setOpmRate(opm);
      setExitPe(exit);
      handleRunProjection({ revenue_growth_rate_pct: g, target_opm_pct: opm, target_exit_pe: exit }, "Bear Case (-30% Drag)");
    } else {
      setGrowthRate(baseGrowth);
      setOpmRate(baseOpm);
      setExitPe(pe);
      handleRunProjection({ revenue_growth_rate_pct: baseGrowth, target_opm_pct: baseOpm, target_exit_pe: pe }, "Base Case (Historical Run-rate)");
    }
  };

  // Prepare chart datasets
  const quarterlyTrends = stock.analytics?.quarterly_analysis?.trends || [];
  const fcfTrends = stock.analytics?.cash_flow_quality?.fcf_trends || [];
  const bsTrends = stock.analytics?.balance_sheet_efficiency?.bs_trends || [];
  const latestQuarterTrend = quarterlyTrends[quarterlyTrends.length - 1];
  const latestFcfTrend = fcfTrends[fcfTrends.length - 1];
  const previousFcfTrend = fcfTrends[fcfTrends.length - 2];
  const latestBsTrend = bsTrends[bsTrends.length - 1];
  const previousBsTrend = bsTrends[bsTrends.length - 2];
  const fcfChartData = fcfTrends.map(row => ({
    period: row.period,
    pat_cr: row.reported_pat_cr,
    cfo_cr: row.reported_cfo_cr,
    fcf_cr: row.stocker_derived_fcf_cr
  }));

  const bankFundingChartData = stock.balance_sheet.periods.map(period => {
    const depRow = findStatementRow(stock.balance_sheet, ['deposits', 'total deposits']);
    const advRow = findStatementRow(stock.balance_sheet, ['advances', 'loans & advances', 'loans and advances']);
    const borRow = findStatementRow(stock.balance_sheet, ['borrowings']);
    return {
      period,
      deposits_cr: depRow?.values[period] ?? null,
      advances_cr: advRow?.values[period] ?? null,
      borrowings_cr: borRow?.values[period] ?? null,
    };
  });

  const npaStatement = stock.quarters.periods.length > 0 ? stock.quarters : stock.profit_loss;
  const bankNpaChartData = npaStatement.periods.map(period => {
    const gnpaRow = findStatementRow(stock.quarters, ['gross npa %', 'gross npa']) || findStatementRow(stock.profit_loss, ['gross npa %', 'gross npa']);
    const nnpaRow = findStatementRow(stock.quarters, ['net npa %', 'net npa']) || findStatementRow(stock.profit_loss, ['net npa %', 'net npa']);
    return {
      period,
      gross_npa_pct: gnpaRow?.values[period] ?? null,
      net_npa_pct: nnpaRow?.values[period] ?? null,
    };
  });
  const hasNpaData = bankNpaChartData.some(d => isFiniteNumber(d.gross_npa_pct) || isFiniteNumber(d.net_npa_pct));

  const quarterSales = latestRowPair(stock.quarters, ['sales', 'revenue']);
  const quarterPat = latestRowPair(stock.quarters, ['net profit', 'pat']);
  const quarterOpm = latestRowPair(stock.quarters, ['opm %', 'operating profit margin']);
  const annualOpm = latestRowPair(stock.profit_loss, ['opm %', 'operating profit margin']);
  const annualPat = latestRowPair(stock.profit_loss, ['net profit', 'pat']);

  const businessModel = stock.financial_business_model || stock.analytics?.financial_business_model || 'GENERAL_CORPORATE';
  const isFinancialBusiness = ['BANK', 'NBFC_LENDER', 'INSURANCE', 'OTHER_FINANCIAL'].includes(businessModel);
  const isBank = (businessModel === 'BANK');

  const latestPlPeriod = stock.profit_loss.periods[stock.profit_loss.periods.length - 1] || '';
  const isPlTTM = latestPlPeriod.trim().toUpperCase() === 'TTM';
  const priorPlPeriod = stock.profit_loss.periods[stock.profit_loss.periods.length - 2] || 'prior FY';

  const quarterlySummary: StatementSummaryItem[] = [
    {
      label: 'Revenue',
      value: formatCrores(quarterSales.current),
      detail: latestQuarterTrend?.sales_growth_yoy_pct !== undefined
        ? <ExplicitChangeIndicator value={latestQuarterTrend.sales_growth_yoy_pct} label="YoY" />
        : <ChangeIndicator metric={quarterSales.metric} current={quarterSales.current} previous={quarterSales.previous} />,
      tone: toneFromSignedValue(latestQuarterTrend?.sales_growth_yoy_pct),
      provenance: latestQuarterTrend?.provenance?.sales_growth_yoy || latestQuarterTrend?.provenance?.sales
    },
    {
      label: 'PAT',
      value: formatCrores(quarterPat.current),
      detail: latestQuarterTrend?.pat_growth_yoy_pct !== undefined
        ? <ExplicitChangeIndicator value={latestQuarterTrend.pat_growth_yoy_pct} label="YoY" />
        : <ChangeIndicator metric={quarterPat.metric} current={quarterPat.current} previous={quarterPat.previous} />,
      tone: toneFromSignedValue(latestQuarterTrend?.pat_growth_yoy_pct),
      provenance: latestQuarterTrend?.provenance?.pat_growth_yoy || latestQuarterTrend?.provenance?.net_profit
    },
    {
      label: 'OPM',
      concept: 'opm',
      value: formatPercent(quarterOpm.current),
      detail: <ChangeIndicator metric={quarterOpm.metric} current={quarterOpm.current} previous={quarterOpm.previous} />,
      tone: toneFromSignedValue((quarterOpm.current ?? 0) - (quarterOpm.previous ?? 0)),
      provenance: latestQuarterTrend?.provenance?.opm_pct
    },
    {
      label: 'QoQ momentum',
      concept: 'qoq',
      value: isFiniteNumber(latestQuarterTrend?.sales_growth_qoq_pct) ? `${latestQuarterTrend.sales_growth_qoq_pct > 0 ? '+' : ''}${latestQuarterTrend.sales_growth_qoq_pct.toFixed(1)}%` : '—',
      detail: <ExplicitChangeIndicator value={latestQuarterTrend?.sales_growth_qoq_pct} label="Sales" />,
      tone: toneFromSignedValue(latestQuarterTrend?.sales_growth_qoq_pct),
      provenance: latestQuarterTrend?.provenance?.sales_growth_qoq
    }
  ];

  const annualSummary: StatementSummaryItem[] = [
    {
      label: '3Y Sales CAGR',
      concept: 'sales_cagr',
      value: formatPercent(stock.analytics?.growth_rates?.sales_cagr_3yr),
      detail: 'Backend-calculated annual growth',
      tone: toneFromSignedValue(stock.analytics?.growth_rates?.sales_cagr_3yr),
      onDetails: () => setSelectedFormulaKey('sales_cagr_3yr'),
      provenance: stock.analytics?.provenance?.sales_cagr_3yr
    },
    {
      label: '3Y PAT CAGR',
      concept: 'pat_cagr',
      value: formatPercent(stock.analytics?.growth_rates?.pat_cagr_3yr),
      detail: 'Backend-calculated annual growth',
      tone: toneFromSignedValue(stock.analytics?.growth_rates?.pat_cagr_3yr),
      onDetails: () => setSelectedFormulaKey('pat_cagr_3yr'),
      provenance: stock.analytics?.provenance?.pat_cagr_3yr
    },
    {
      label: isPlTTM ? 'TTM OPM' : 'Latest OPM',
      concept: 'opm',
      value: formatPercent(annualOpm.current),
      detail: isPlTTM 
        ? `vs ${priorPlPeriod}` 
        : <ChangeIndicator metric={annualOpm.metric} current={annualOpm.current} previous={annualOpm.previous} />,
      tone: toneFromSignedValue((annualOpm.current ?? 0) - (annualOpm.previous ?? 0))
    },
    {
      label: isPlTTM ? 'TTM PAT' : 'Latest PAT',
      value: formatCrores(annualPat.current),
      detail: isPlTTM
        ? `vs ${priorPlPeriod}`
        : <ChangeIndicator metric={annualPat.metric} current={annualPat.current} previous={annualPat.previous} />,
      tone: annualPat.current !== null && annualPat.current < 0 ? 'negative' : toneFromSignedValue((annualPat.current ?? 0) - (annualPat.previous ?? 0)),
      provenance: latestFcfTrend?.provenance?.pat
    }
  ];

  const cashFlowSummary: StatementSummaryItem[] = isFinancialBusiness ? [
    {
      label: 'Cash Flow Analysis',
      value: 'Not applicable for banking & financial institutions',
      detail: 'Operating cash flows are dominated by customer deposit and lending movements',
      tone: 'neutral'
    }
  ] : [
    {
      label: 'CFO',
      concept: 'cfo',
      value: formatCrores(latestFcfTrend?.reported_cfo_cr),
      detail: <ChangeIndicator metric="Cash from Operating Activity" current={latestFcfTrend?.reported_cfo_cr} previous={previousFcfTrend?.reported_cfo_cr} />,
      tone: toneForPositiveMetric(latestFcfTrend?.reported_cfo_cr, previousFcfTrend?.reported_cfo_cr),
      provenance: latestFcfTrend?.provenance?.cfo
    },
    {
      label: '5Y CFO/PAT',
      concept: 'cfo_pat',
      value: formatPercent(stock.analytics?.cash_flow_quality?.cfo_to_pat_5yr_pct),
      detail: stock.analytics?.cash_flow_quality?.cash_conversion_quality || '5-year common period conversion',
      tone: cashConversionTone(stock.analytics?.cash_flow_quality?.cash_conversion_quality),
      onDetails: () => setSelectedFormulaKey('cfo_to_pat_5yr'),
      provenance: stock.analytics?.provenance?.cfo_to_pat_5yr
    },
    {
      label: 'Capex',
      concept: 'capex',
      value: formatCrores(latestFcfTrend?.capex_cr),
      detail: latestFcfTrend?.capex_methodology || 'Neutral: direction needs context',
      tone: 'neutral'
    },
    {
      label: 'FCF',
      concept: 'fcf',
      value: formatCrores(latestFcfTrend?.stocker_derived_fcf_cr),
      detail: latestFcfTrend?.fcf_confidence ? `FCF (${latestFcfTrend.fcf_confidence})` : <ChangeIndicator metric="Free Cash Flow" current={latestFcfTrend?.stocker_derived_fcf_cr} previous={previousFcfTrend?.stocker_derived_fcf_cr} />,
      tone: toneForPositiveMetric(latestFcfTrend?.stocker_derived_fcf_cr, previousFcfTrend?.stocker_derived_fcf_cr),
      onDetails: () => setSelectedFormulaKey('free_cash_flow')
    }
  ];

  const bankDeposits = stock.analytics?.bank_metrics?.latest_deposits_cr ?? latestRowPair(stock.balance_sheet, ['deposits', 'total deposits']).current;
  const bankAdvances = stock.analytics?.bank_metrics?.latest_advances_cr ?? latestRowPair(stock.balance_sheet, ['advances', 'loans & advances']).current;
  const bankGnpa = stock.analytics?.bank_metrics?.latest_gross_npa_pct;
  const bankNnpa = stock.analytics?.bank_metrics?.latest_net_npa_pct;

  const balanceSheetSummary: StatementSummaryItem[] = isBank ? [
    {
      label: 'Deposits',
      value: formatCrores(bankDeposits),
      detail: 'Total customer deposits',
      tone: 'neutral'
    },
    {
      label: 'Borrowings',
      value: formatCrores(latestBsTrend?.borrowings_cr ?? stock.analytics?.balance_sheet_efficiency?.borrowings_cr),
      detail: <ChangeIndicator metric="Borrowings" current={latestBsTrend?.borrowings_cr} previous={previousBsTrend?.borrowings_cr} />,
      tone: 'neutral',
      provenance: latestBsTrend?.provenance?.borrowings
    },
    {
      label: 'Advances / Loans',
      value: formatCrores(bankAdvances),
      detail: 'Loan book size',
      tone: 'neutral'
    },
    {
      label: 'Gross NPA %',
      value: formatPercent(bankGnpa),
      detail: isFiniteNumber(bankNnpa) ? `Net NPA: ${bankNnpa}%` : (bankGnpa === null || bankGnpa === undefined ? 'Bank-specific metric unavailable in current source' : 'Asset Quality'),
      tone: 'neutral'
    }
  ] : [
    {
      label: 'Borrowings',
      value: formatCrores(latestBsTrend?.borrowings_cr ?? stock.analytics?.balance_sheet_efficiency?.borrowings_cr),
      detail: <ChangeIndicator metric="Borrowings" current={latestBsTrend?.borrowings_cr} previous={previousBsTrend?.borrowings_cr} />,
      tone: 'neutral',
      provenance: latestBsTrend?.provenance?.borrowings
    },
    {
      label: 'Debt/Equity',
      concept: 'debt_equity',
      value: isFiniteNumber(stock.analytics?.balance_sheet_efficiency?.latest_debt_to_equity) ? `${stock.analytics.balance_sheet_efficiency.latest_debt_to_equity}x` : '—',
      detail: 'Leverage needs business context',
      tone: 'neutral',
      onDetails: () => setSelectedFormulaKey('debt_to_equity')
    },
    {
      label: 'CWIP',
      concept: 'cwip',
      value: formatCrores(latestBsTrend?.cwip_cr ?? stock.analytics?.balance_sheet_efficiency?.cwip_cr),
      detail: <ChangeIndicator metric="CWIP" current={latestBsTrend?.cwip_cr} previous={previousBsTrend?.cwip_cr} />,
      tone: 'neutral',
      provenance: latestBsTrend?.provenance?.cwip
    },
    {
      label: 'CWIP / Net Block',
      concept: 'cwip',
      value: formatPercent(stock.analytics?.balance_sheet_efficiency?.latest_cwip_to_net_block_pct),
      detail: 'Expansion signal, not automatically good or bad',
      tone: 'neutral'
    }
  ];

  const statementSummary = financialSubTab === 'quarters'
    ? quarterlySummary
    : financialSubTab === 'pl'
      ? annualSummary
      : financialSubTab === 'balance_sheet'
        ? balanceSheetSummary
        : cashFlowSummary;
  const selectedFormula = selectedFormulaKey
    ? stock.analytics?.formula_transparency?.[selectedFormulaKey] ?? null
    : null;
  const projectionUnavailable = researchStatus?.projection === 'unavailable';
  const investmentScoreUnavailable = researchStatus?.investment_score === 'unavailable';
  const lifecycleStatusPending = researchStatus === null;
  const canApplyProjectionPresets = isFiniteNumber(stock.projection.historical_revenue_cagr_3yr) &&
    isFiniteNumber(stock.projection.historical_opm_median) && isFiniteNumber(stock.ratios.stock_pe);
  const legacyDocumentCount = isFiniteNumber(stock.documents?.diagnostics?.ai_ready_documents_count)
    ? stock.documents.diagnostics.ai_ready_documents_count
    : (stock.documents?.annual_reports?.length || 0) +
      (stock.documents?.concalls?.length || 0) +
      (stock.documents?.presentations?.length || 0) +
      (stock.documents?.material_announcements?.length || 0);
  const businessAnalysisFilingBadge = filingDiscoveryState === 'running'
    ? 'Searching…'
    : researchStatus
      ? researchStatus.source_filings === 'not_searched'
        ? 'Not searched'
        : `${researchStatus.filing_count} Filings`
      : legacyDocumentCount > 0
        ? `${legacyDocumentCount} Links`
        : 'No links';

  const formatConfidence = (confidence?: number) => {
    if (!isFiniteNumber(confidence)) return null;
    return `${Math.round(confidence <= 1 ? confidence * 100 : confidence)}% confidence`;
  };

  return (
    <div className="space-y-6 pb-12">
      
      {/* Back Button & Dossier Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="text-xs font-bold text-slate-400 hover:text-emerald-400 flex items-center gap-1.5 transition-colors bg-slate-900 px-3 py-1.5 rounded-xl border border-slate-800"
        >
          <span>← Back to Universe Leaderboard</span>
        </button>

        <div className="flex items-center gap-2">
          {onScrapeRefresh && (
            <button
              onClick={onScrapeRefresh}
              disabled={isFinancialRefreshing}
              className="text-xs font-semibold text-slate-300 hover:text-emerald-400 flex items-center gap-1.5 bg-slate-900 px-3 py-1.5 rounded-xl border border-slate-800 transition-colors"
              title="Refresh financial data for this resolved stock"
            >
              <RefreshCw className={`w-3 h-3 text-emerald-400 ${isFinancialRefreshing ? 'animate-spin' : ''}`} />
              <span>{isFinancialRefreshing ? 'Refreshing Financials…' : 'Refresh Financial Data'}</span>
            </button>
          )}
          <a
            href={stock.source_url || `https://www.screener.in/company/${stock.symbol}/consolidated/`}
            target="_blank"
            rel="noreferrer"
            className="text-xs font-semibold text-slate-400 hover:text-slate-200 flex items-center gap-1 bg-slate-900/80 px-3 py-1.5 rounded-xl border border-slate-800"
          >
            <span>View on {stock.source_name || 'Screener.in'} ({stock.statement_type || 'consolidated'})</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>

      {/* Hero Stock Overview Card */}
      <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
          
          {/* Company Title & Price */}
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-extrabold text-white tracking-tight">{stock.name}</h1>
              <span className="text-xs font-mono font-bold px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                Ticker: {stock.symbol}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 font-medium">
              <span className="flex items-center gap-1">
                <Building className="w-3.5 h-3.5 text-slate-500" />
                {stock.sector}
              </span>
              <span>•</span>
              <span>{stock.industry}</span>
              <span>•</span>
              <span>High/Low: {stock.ratios.high_low?.trim() || '—'}</span>
            </div>
            <div className="flex flex-wrap items-center gap-2.5 text-[11px] text-slate-400 font-mono">
              <span className="font-semibold flex items-center gap-1.5">
                <DataOriginBadge origin="reported_fact" /> {stock.source_name || 'Screener.in'} ({stock.statement_type || 'consolidated'})
              </span>
              {stock.fetched_at && (
                <>
                  <span className="text-slate-600">•</span>
                  <span className="text-slate-300">
                    Raw Data Fetched: {new Date(stock.fetched_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })} {new Date(stock.fetched_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </>
              )}
              {stock.documents_checked_at && (
                <>
                  <span className="text-slate-600">•</span>
                  <span className="text-cyan-300 flex items-center gap-1">
                    <FileText className="w-3 h-3 text-cyan-400" />
                    Document Sources Checked: {new Date(stock.documents_checked_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })} {new Date(stock.documents_checked_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </>
              )}
              {docIntel?.extraction_timestamp && (
                <>
                  <span className="text-slate-600">•</span>
                  <span className="text-amber-300 flex items-center gap-1">
                    <Sparkles className="w-3 h-3 text-amber-400" />
                    AI Analysis Last Run: {new Date(docIntel.extraction_timestamp).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })} {new Date(docIntel.extraction_timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </>
              )}
              {stock.financial_truth && (
                <>
                  <span className="text-slate-600">•</span>
                  <span className="text-emerald-300 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                    Financial Truth: {stock.financial_truth.verified_count}/{stock.financial_truth.coverage?.total_tracked_facts ?? 0} Facts Verified
                    {(stock.financial_truth.discrepancies_count ?? 0) > 0 && (
                      <span className="text-amber-400 font-semibold ml-1">
                        ({stock.financial_truth.discrepancies_count} Discrepancies)
                      </span>
                    )}
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Price & Composite Score Badges */}
          <div className="flex flex-wrap items-center gap-4 bg-slate-950/80 p-4 rounded-2xl border border-slate-800">
            <div>
              <span className="text-[10px] text-slate-500 uppercase font-mono block">Current Price</span>
              <span className="text-2xl font-extrabold font-mono text-white">
                {formatRupees(stock.ratios.current_price)}
              </span>
            </div>
            <div className="h-10 w-[1px] bg-slate-800 hidden sm:block" />
            <div>
              <span className="text-[10px] text-slate-500 uppercase font-mono block"><ConceptHelp term="market_cap" label="Market Cap" /></span>
              <span className="text-sm font-bold font-mono text-slate-200">
                {formatCrores(stock.ratios.market_cap_cr)}
              </span>
            </div>
            <div className="h-10 w-[1px] bg-slate-800 hidden sm:block" />
            <div className="text-right">
              <span className="text-[10px] text-slate-500 uppercase font-mono block">Investability Score</span>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-xl font-extrabold font-mono text-emerald-400">
                  {investmentScoreUnavailable ? '—' : `${stock.score.total_composite_score}/100`}
                </span>
                {researchStatus && !investmentScoreUnavailable && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">{stock.score.verdict}</span>
                )}
              </div>
              {lifecycleStatusPending && <span className="text-[10px] text-slate-500">Research classification pending</span>}
            </div>
          </div>

        </div>

        {/* 8 Primary Financial Ratio Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 font-mono">
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-center">
            <span className="text-[10px] text-slate-500 uppercase font-sans block"><ConceptHelp term="pe" label="Stock P/E" /></span>
            <span className="text-sm font-bold text-slate-100">{formatMultiple(stock.ratios.stock_pe)}</span>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-center">
            <span className="text-[10px] text-slate-500 uppercase font-sans block"><ConceptHelp term="roce" label="ROCE" /></span>
            <span className="text-sm font-bold text-emerald-400">{formatPercent(stock.ratios.roce_pct)}</span>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-center">
            <span className="text-[10px] text-slate-500 uppercase font-sans block"><ConceptHelp term="roe" label="ROE" /></span>
            <span className="text-sm font-bold text-cyan-400">{formatPercent(stock.ratios.roe_pct)}</span>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-center relative group">
            <div className="flex items-center justify-center gap-1">
              <span className="text-[10px] text-slate-500 uppercase font-sans block">
                <ConceptHelp term="fcf" label="FCF Yield" onCalculationDetails={() => setSelectedFormulaKey('free_cash_flow')} />
              </span>
            </div>
            <span className="text-sm font-bold text-teal-400">{formatPercent(stock.ratios.fcf_yield_pct)}</span>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-center relative group">
            <div className="flex items-center justify-center gap-1">
              <span className="text-[10px] text-slate-500 uppercase font-sans block">
                <ConceptHelp term="sales_cagr" label="3Y Sales CAGR" onCalculationDetails={() => setSelectedFormulaKey('sales_cagr_3yr')} />
              </span>
            </div>
            <span className="text-sm font-bold text-slate-100">
              {formatPercent(stock.analytics?.growth_rates?.sales_cagr_3yr ?? stock.ratios.sales_growth_3yr_cagr)}
            </span>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-center relative group">
            <div className="flex items-center justify-center gap-1">
              <span className="text-[10px] text-slate-500 uppercase font-sans block">
                <ConceptHelp term="cfo_pat" label="CFO / PAT (5Y)" onCalculationDetails={() => setSelectedFormulaKey('cfo_to_pat_5yr')} />
              </span>
            </div>
            <span className="text-sm font-bold text-emerald-400">
              {formatPercent(stock.analytics?.cash_flow_quality?.cfo_to_pat_5yr_pct)}
            </span>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-center relative group">
            <div className="flex items-center justify-center gap-1">
              <span className="text-[10px] text-slate-500 uppercase font-sans block">
                <ConceptHelp term="debt_equity" label="Debt / Equity" onCalculationDetails={() => setSelectedFormulaKey('debt_to_equity')} />
              </span>
            </div>
            <span className="text-sm font-bold text-slate-100">{isFiniteNumber(stock.ratios.debt_to_equity) ? `${stock.ratios.debt_to_equity}x` : '—'}</span>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-center">
            <span className="text-[10px] text-slate-500 uppercase font-sans block">Div Yield</span>
            <span className="text-sm font-bold text-slate-100">{formatPercent(stock.ratios.dividend_yield_pct)}</span>
          </div>
        </div>

        {/* Company About Snippet */}
        <p className="layout-reading text-xs text-slate-400 leading-relaxed bg-slate-900/40 p-3.5 rounded-xl border border-slate-800/60">
          <strong className="text-slate-200">About Company:</strong> {stock.about}
        </p>
      </div>

      <ResearchStatusPanel
        status={researchStatus}
        loading={researchStatusLoading}
        error={researchStatusError}
        filingDiscoveryState={filingDiscoveryState}
        verificationState={verificationState}
        businessAnalysisRunning={generatingDocIntel}
        onRetryStatus={onRefreshResearchStatus}
        onRetryFilings={onRetryFilings}
        onRetryVerification={onRetryVerification}
        onRunAnalysis={handleGenerateIntel}
      />

      {/* LEVEL 2: 60-SECOND INVESTMENT THESIS & CONVICTION CARD */}
      <div className="glass-panel rounded-3xl p-6 md:p-7 border border-slate-800 bg-gradient-to-br from-slate-950 via-slate-900/90 to-slate-950 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
          <div className="flex items-center gap-2.5">
            <Sparkles className="w-5 h-5 text-emerald-400" />
            <h3 className="text-base font-bold text-white tracking-wide">60-Second Investment Thesis & Conviction Card</h3>
            <DataOriginBadge origin="stocker_calculation" />
          </div>
          <div className="flex items-center gap-2">
            {researchStatus && (
              <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border ${researchStatus.investment_score === 'evidence_enriched' ? 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30' : 'bg-amber-500/10 text-amber-300 border-amber-500/30'}`}>
                {researchStatus.investment_score === 'provisional' ? 'Provisional — financial analysis only' : researchStatus.investment_score === 'evidence_enriched' ? 'Evidence-enriched' : researchStatus.investment_score === 'incomplete' ? 'Incomplete research' : 'Score not available'}
              </span>
            )}
            {lifecycleStatusPending && <span className="text-[10px] text-slate-400 border border-slate-700 rounded-full px-2.5 py-0.5">Research classification pending</span>}
            {!investmentScoreUnavailable && <>
              {researchStatus && <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">{stock.score.verdict}</span>}
              <span className="text-[11px] font-mono text-slate-400 bg-slate-900 px-2.5 py-0.5 rounded-lg border border-slate-800">Score: {stock.score.total_composite_score}/100</span>
            </>}
          </div>
        </div>

        {/* Core Thesis Paragraph */}
        <p className="layout-reading text-xs text-slate-200 leading-relaxed bg-slate-900/60 p-4 rounded-2xl border border-slate-800/80">
          <strong className="text-emerald-400 font-semibold uppercase tracking-wider text-[11px] block mb-1">The Core Buy Thesis:</strong>
          {stock.score.investment_thesis}
        </p>

        {/* 4-Box Key Highlights Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3.5 text-xs">
          
          {/* 1. Promise vs Delivery */}
          <div className="bg-slate-950/70 p-3.5 rounded-2xl border border-slate-800/80 space-y-1.5 flex flex-col justify-between">
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider flex items-center gap-1">
              <Target className="w-3.5 h-3.5 text-cyan-400" />
              Management Execution
            </span>
            {docIntel?.promise_vs_delivery && docIntel.promise_vs_delivery.length > 0 ? (
              <div>
                <div className="flex items-center gap-1.5 font-mono text-xs my-1">
                  <span className="text-emerald-400 font-bold">✓ {docIntel.promise_vs_delivery.filter(p => p.status === 'Delivered').length} Delivered</span>
                  <span className="text-slate-500">|</span>
                  <span className="text-amber-400 font-bold">⚠ {docIntel.promise_vs_delivery.filter(p => p.status === 'In Progress').length} In Progress</span>
                  {docIntel.promise_vs_delivery.filter(p => p.status === 'Missed').length > 0 && (
                    <>
                      <span className="text-slate-500">|</span>
                      <span className="text-rose-400 font-bold">✗ {docIntel.promise_vs_delivery.filter(p => p.status === 'Missed').length} Missed</span>
                    </>
                  )}
                </div>
                <p className="text-[11px] text-slate-400 leading-tight line-clamp-2">
                  {docIntel.promise_vs_delivery[0]?.actual_outcome || 'Outcome evidence unavailable.'}
                </p>
              </div>
            ) : (
              <p className="text-[11px] text-slate-400 italic">
                Execution track record has not been analyzed yet.
              </p>
            )}
          </div>

          {/* 2. Future Growth Drivers */}
          <div className="bg-slate-950/70 p-3.5 rounded-2xl border border-slate-800/80 space-y-1.5 flex flex-col justify-between">
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider flex items-center gap-1">
              <Layers className="w-3.5 h-3.5 text-amber-400" />
              Key Growth Driver
            </span>
            <div>
              <p className="text-xs font-semibold text-slate-200 line-clamp-1">
                {docIntel?.growth_drivers?.[0]?.driver_title || stock.score.key_catalysts[0] || 'No sourced growth driver'}
              </p>
              <p className="text-[11px] text-slate-400 leading-tight line-clamp-2 mt-0.5">
                {docIntel?.growth_drivers?.[0]?.description || 'No filing-backed expansion detail is currently available.'}
              </p>
            </div>
          </div>

          {/* 3. Forensic Cash Check / Bank Asset Quality */}
          <div className="bg-slate-950/70 p-3.5 rounded-2xl border border-slate-800/80 space-y-1.5 flex flex-col justify-between">
            {isBank ? (
              <>
                <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                  Asset Quality & Funding
                </span>
                <div>
                  <div className="flex items-center gap-2 font-mono text-xs my-1">
                    <span className="text-cyan-300 font-bold">Deposits: {formatCrores(bankDeposits)}</span>
                  </div>
                  <p className="text-[11px] text-slate-400 leading-tight">
                    GNPA: <strong className="text-slate-200">{formatPercent(bankGnpa)}</strong> | NNPA: <strong className="text-slate-200">{formatPercent(bankNnpa)}</strong> | Advances: <strong className="text-slate-200">{formatCrores(bankAdvances)}</strong>
                  </p>
                </div>
              </>
            ) : isFinancialBusiness ? (
              <>
                <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-slate-400" />
                  Financial Model Safety
                </span>
                <div>
                  <p className="text-[11px] text-slate-400 leading-snug italic my-1">
                    Sector-specific financial quality model pending. Industrial CFO/CWIP metrics are not applicable.
                  </p>
                </div>
              </>
            ) : (
              <>
                <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  Cash Conversion & Safety
                </span>
                <div>
                  <div className="flex items-center gap-2 font-mono text-xs my-1">
                    <span className="text-emerald-400 font-bold">5Y CFO/PAT: {formatPercent(stock.analytics?.cash_flow_quality?.cfo_to_pat_5yr_pct)}</span>
                  </div>
                  <p className="text-[11px] text-slate-400 leading-tight">
                    Debt/Equity: <strong className="text-slate-200">{isFiniteNumber(stock.ratios.debt_to_equity) ? `${stock.ratios.debt_to_equity}x` : '—'}</strong> | CWIP: <strong className="text-slate-200">{formatPercent(stock.analytics?.balance_sheet_efficiency?.latest_cwip_to_net_block_pct)}</strong>
                  </p>
                </div>
              </>
            )}
          </div>

          {/* 4. Valuation Scenario Bridge */}
          <div className="bg-slate-950/70 p-3.5 rounded-2xl border border-slate-800/80 space-y-1.5 flex flex-col justify-between">
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider flex items-center gap-1">
              <TrendingUp className="w-3.5 h-3.5 text-purple-400" />
              Valuation Bridge (3Y)
            </span>
            {isFinancialBusiness ? (
              <p className="text-[11px] text-slate-400 leading-snug italic">
                Sector-specific projection model not implemented yet. Industrial DCF is suppressed.
              </p>
            ) : lifecycleStatusPending ? (
              <p className="text-[11px] text-slate-400 leading-snug">Research classification pending. Latest stored values remain available in the projection model.</p>
            ) : projectionUnavailable ? (
              <p className="text-[11px] text-slate-400 leading-snug">Projection unavailable with current evidence.</p>
            ) : (
              <div className="space-y-1">
                <div className="flex items-center justify-between text-[11px] font-mono">
                  <span className="text-slate-500">Base DCF:</span>
                  <span className="text-emerald-400 font-bold">₹{stock.projection.dcf_fair_value_per_share} ({stock.projection.dcf_upside_pct > 0 ? `+${stock.projection.dcf_upside_pct}%` : `${stock.projection.dcf_upside_pct}%`})</span>
                </div>
                <div className="flex items-center justify-between text-[11px] font-mono">
                  <span className="text-slate-500">Target (Exit P/E):</span>
                  <span className="text-purple-300 font-bold">₹{stock.projection.target_price_exit_pe} ({stock.projection.target_price_upside_pct > 0 ? `+${stock.projection.target_price_upside_pct}%` : `${stock.projection.target_price_upside_pct}%`})</span>
                </div>
              </div>
            )}
          </div>

        </div>
      </div>

      {/* Main Tabbed Navigation Bar */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2 overflow-x-auto">
        <button
          onClick={() => setActiveTab('projection')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === 'projection'
              ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <Sliders className="w-3.5 h-3.5" />
          <span>Interactive Projections & DCF Model</span>
        </button>

        <button
          onClick={() => setActiveTab('outlook')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === 'outlook'
              ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <Compass className="w-3.5 h-3.5" />
          <span>Business Analysis</span>
          <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono border ${
            activeTab === 'outlook'
              ? 'bg-slate-950 text-emerald-300 border-emerald-500/30'
              : 'bg-slate-900 text-slate-400 border-slate-700'
          }`}>
            {businessAnalysisFilingBadge}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('financials')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === 'financials'
              ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <FileSpreadsheet className="w-3.5 h-3.5" />
          <span>Financial Statements (Raw Screener)</span>
        </button>

        <button
          onClick={() => setActiveTab('charts')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === 'charts'
              ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <BarChart3 className="w-3.5 h-3.5" />
          <span>Trend Analytics & Visualizations</span>
        </button>

        <button
          onClick={() => setActiveTab('scorecard')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === 'scorecard'
              ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>5-Pillar Scorecard & Risks</span>
        </button>
      </div>

      {/* TAB 1: INTERACTIVE PROJECTIONS & DCF VALUATION */}
      {activeTab === 'projection' && (
        <div className="space-y-6">
          {isFinancialBusiness ? (
            <div className="glass-panel rounded-3xl p-8 border border-slate-800 text-center space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center mx-auto text-amber-400">
                <Sliders className="w-6 h-6" />
              </div>
              <div className="space-y-2 max-w-lg mx-auto">
                <h3 className="text-base font-bold text-white">Sector-Specific Projection Model Pending</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Corporate Discounted Cash Flow (DCF) and Free Cash Flow projections are not applicable to banking and financial institutions because operating cash flows and capital structures are fundamentally different. A specialized financial institutions valuation model is planned for a future phase.
                </p>
              </div>
            </div>
          ) : (
            <>
              {lifecycleStatusPending && (
                <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4 flex items-start gap-3">
                  <Info className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-bold text-slate-200">Projection classification pending</p>
                    <p className="text-[11px] text-slate-400 mt-1">Showing the latest stored projection while Stocker loads its research lifecycle classification.</p>
                  </div>
                </div>
              )}
              {researchStatus && (
                <div className={`rounded-2xl border p-4 flex items-start gap-3 ${researchStatus.projection === 'evidence_enriched' ? 'bg-emerald-950/30 border-emerald-800/50' : researchStatus.projection === 'stale' ? 'bg-amber-950/30 border-amber-800/50' : 'bg-slate-950/70 border-slate-800'}`}>
                  {researchStatus.projection === 'stale' ? <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" /> : <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />}
                  <div>
                    <p className="text-xs font-bold text-slate-100">
                      {researchStatus.projection === 'historical_only' ? 'Preliminary / Historical-only' : researchStatus.projection === 'evidence_enriched' ? 'Evidence-enriched' : researchStatus.projection === 'stale' ? 'Business evidence changed. Projection needs refresh.' : 'Projection unavailable with current evidence.'}
                    </p>
                    <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                      {researchStatus.projection === 'historical_only' ? 'Based on available historical financial evidence. Run Business Analysis to incorporate management guidance, capacity plans, demand drivers and execution history.' : researchStatus.projection === 'evidence_enriched' ? 'Company filing and business evidence has been incorporated into this projection.' : researchStatus.projection === 'stale' ? 'Refresh the projection before relying on valuation outputs.' : 'Stocker does not have enough supported evidence to present a valid projection or DCF.'}
                    </p>
                  </div>
                </div>
              )}
              {!projectionUnavailable && <>
          
          {/* Projections Control Panel */}
          <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-emerald-400" />
                  Dynamic 5-Year Projection & Valuation Simulator
                  <ConceptHelp term="stocker_projection" />
                </h3>
                <p className="text-xs text-slate-400">
                  Simulate future revenue growth, margin expansion, and exit multiple to calculate DCF Fair Value and Expected IRR
                </p>
              </div>
              <div className="flex items-center gap-2">
                {isProjecting && (
                  <span className="text-[11px] text-cyan-300 flex items-center gap-1.5" role="status">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Refreshing projection…
                  </span>
                )}
                <DataOriginBadge origin="stocker_projection" />
              </div>

              {/* Scenario Presets */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => applyPreset('bear')}
                  disabled={!canApplyProjectionPresets}
                  title={canApplyProjectionPresets ? 'Apply bear scenario' : 'Historical growth, margin, and P/E are required for presets'}
                  className="px-3 py-1 rounded-lg text-xs font-semibold bg-rose-950/50 text-rose-300 border border-rose-800 hover:bg-rose-900/50 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Bear Case
                </button>
                <button
                  onClick={() => applyPreset('base')}
                  disabled={!canApplyProjectionPresets}
                  title={canApplyProjectionPresets ? 'Apply historical base scenario' : 'Historical growth, margin, and P/E are required for presets'}
                  className="px-3 py-1 rounded-lg text-xs font-semibold bg-slate-800 text-slate-200 border border-slate-700 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Base Case
                </button>
                <button
                  onClick={() => applyPreset('bull')}
                  disabled={!canApplyProjectionPresets}
                  title={canApplyProjectionPresets ? 'Apply bull scenario' : 'Historical growth, margin, and P/E are required for presets'}
                  className="px-3 py-1 rounded-lg text-xs font-semibold bg-emerald-950/50 text-emerald-300 border border-emerald-800 hover:bg-emerald-900/50 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Bull Case
                </button>
              </div>
            </div>

            {/* Slider Controls */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 pt-2">
              
              {/* Revenue CAGR Slider */}
              <div className="space-y-2 bg-slate-950/60 p-4 rounded-2xl border border-slate-800">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400 font-medium"><ConceptHelp term="sales_cagr" label="Forward Sales CAGR" /></span>
                  <span className="font-mono font-bold text-emerald-400">{growthRate}%</span>
                </div>
                <input
                  type="range"
                  min="2"
                  max="35"
                  step="0.5"
                  value={growthRate}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value);
                    setGrowthRate(val);
                    handleRunProjection({ revenue_growth_rate_pct: val });
                  }}
                  className="w-full accent-emerald-500 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>2% (Cautious)</span>
                  <span>Hist 3Y: {formatPercent(stock.projection.historical_revenue_cagr_3yr)}</span>
                  <span>35%</span>
                </div>
              </div>

              {/* Target OPM % Slider */}
              <div className="space-y-2 bg-slate-950/60 p-4 rounded-2xl border border-slate-800">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400 font-medium"><ConceptHelp term="opm" label="Target OPM (Margin)" /></span>
                  <span className="font-mono font-bold text-cyan-400">{opmRate}%</span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="60"
                  step="0.5"
                  value={opmRate}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value);
                    setOpmRate(val);
                    handleRunProjection({ target_opm_pct: val });
                  }}
                  className="w-full accent-cyan-500 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>5%</span>
                  <span>Median: {formatPercent(stock.projection.historical_opm_median)}</span>
                  <span>60%</span>
                </div>
              </div>

              {/* Capex Intensity Slider */}
              <div className="space-y-2 bg-slate-950/60 p-4 rounded-2xl border border-slate-800">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400 font-medium"><ConceptHelp term="capex" label="Capex % of Sales" /></span>
                  <span className="font-mono font-bold text-slate-200">{capexRate}%</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="20"
                  step="0.5"
                  value={capexRate}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value);
                    setCapexRate(val);
                    handleRunProjection({ capex_pct_of_sales: val });
                  }}
                  className="w-full accent-emerald-500 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>1% (Asset-light)</span>
                  <span>20% (Heavy Capex)</span>
                </div>
              </div>

              {/* Exit Multiple Slider */}
              <div className="space-y-2 bg-slate-950/60 p-4 rounded-2xl border border-slate-800">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400 font-medium"><ConceptHelp term="pe" label="Target Exit P/E" /></span>
                  <span className="font-mono font-bold text-amber-400">{exitPe}x</span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="65"
                  step="1"
                  value={exitPe}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value);
                    setExitPe(val);
                    handleRunProjection({ target_exit_pe: val });
                  }}
                  className="w-full accent-amber-500 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>10x</span>
                  <span>Current: {formatMultiple(stock.ratios.stock_pe)}</span>
                  <span>65x</span>
                </div>
              </div>

            </div>

            {/* Valuation Results Highlight Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
              
              {/* DCF Fair Value Card */}
              <div className="bg-gradient-to-br from-emerald-950/40 to-slate-950 p-5 rounded-2xl border border-emerald-500/30 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider"><ConceptHelp term="dcf" label="DCF Intrinsic Fair Value" /></span>
                  <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded-full ${
                    projectionResult.dcf_upside_pct >= 0 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                  }`}>
                    {projectionResult.dcf_upside_pct >= 0 ? `+${projectionResult.dcf_upside_pct}% Upside` : `${projectionResult.dcf_upside_pct}% Margin`}
                  </span>
                </div>
                <div className="text-3xl font-extrabold font-mono text-white">
                  ₹{projectionResult.dcf_fair_value_per_share.toLocaleString('en-IN')}
                </div>
                <p className="text-[11px] text-slate-400">
                  Discounted Cash Flow based on 5-year FCFs + <ConceptHelp term="terminal_growth" label={`${terminalG}% Terminal Growth`} /> @ <ConceptHelp term="wacc" label={`${wacc}% WACC`} />.
                </p>
              </div>

              {/* Exit Multiple Target Price */}
              <div className="bg-gradient-to-br from-cyan-950/40 to-slate-950 p-5 rounded-2xl border border-cyan-500/30 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-cyan-400 uppercase tracking-wider"><ConceptHelp term="pe" label="FY28 Exit P/E Target Price" /></span>
                  <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded-full ${
                    projectionResult.target_price_upside_pct >= 0 ? 'bg-cyan-500/20 text-cyan-300' : 'bg-rose-500/20 text-rose-300'
                  }`}>
                    {projectionResult.target_price_upside_pct >= 0 ? `+${projectionResult.target_price_upside_pct}% Target` : `${projectionResult.target_price_upside_pct}%`}
                  </span>
                </div>
                <div className="text-3xl font-extrabold font-mono text-white">
                  ₹{projectionResult.target_price_exit_pe.toLocaleString('en-IN')}
                </div>
                <p className="text-[11px] text-slate-400">
                  {isFiniteNumber(projectionResult.projections[2]?.eps)
                    ? `Based on Projected Year 3 EPS (₹${formatIndianNumber(projectionResult.projections[2].eps)}) × ${exitPe}x Exit Multiple.`
                    : 'Projected Year 3 EPS is unavailable.'}
                </p>
              </div>

              {/* Projected 3-Year IRR */}
              <div className="bg-gradient-to-br from-teal-950/40 to-slate-950 p-5 rounded-2xl border border-teal-500/30 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-teal-400 uppercase tracking-wider"><ConceptHelp term="irr" label="Projected 3-Year CAGR / IRR" /></span>
                  <span className="text-xs font-bold text-teal-300">
                    {projectionResult.scenario_type}
                  </span>
                </div>
                <div className="text-3xl font-extrabold font-mono text-emerald-400">
                  {projectionResult.projected_3yr_irr_cagr_pct}% / yr
                </div>
                <p className="text-[11px] text-slate-400">
                  Expected annual compounding rate from current price {formatRupees(stock.ratios.current_price)}.
                </p>
              </div>

            </div>
          </div>

          {/* 5-Year Forward Projection Financial Table */}
          <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
            <h4 className="font-bold text-white text-base">5-Year Forward Forecast Table (₹ in Cr)</h4>
            
            <div className="overflow-x-auto rounded-2xl border border-slate-800 font-mono text-xs">
              <table className="w-full text-left">
                <thead className="bg-slate-900 text-slate-400 uppercase tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="py-3 px-4 sticky left-0 bg-slate-900 z-10 font-sans font-bold text-slate-300">
                      Forecast Line Item
                    </th>
                    {projectionResult.projections.map(p => (
                      <th key={p.year} className="py-3 px-4 text-right whitespace-nowrap text-emerald-400 font-bold">
                        {p.year}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  <tr className="hover:bg-slate-900/50 bg-slate-900/20 font-semibold text-slate-100">
                    <td className="py-2.5 px-4 sticky left-0 bg-slate-900 text-emerald-400 font-sans font-bold">
                      Projected Revenue
                    </td>
                    {projectionResult.projections.map(p => (
                      <td key={p.year} className="py-2.5 px-4 text-right">₹{p.revenue_cr.toLocaleString('en-IN')}</td>
                    ))}
                  </tr>

                  <tr className="hover:bg-slate-900/50 text-slate-300">
                    <td className="py-2.5 px-4 sticky left-0 bg-slate-950 font-sans">
                      <ConceptHelp term="ebitda" label="Operating Profit (EBITDA)" />
                    </td>
                    {projectionResult.projections.map(p => (
                      <td key={p.year} className="py-2.5 px-4 text-right">₹{p.ebitda_cr.toLocaleString('en-IN')} ({p.opm_pct}%)</td>
                    ))}
                  </tr>

                  <tr className="hover:bg-slate-900/50 text-slate-300">
                    <td className="py-2.5 px-4 sticky left-0 bg-slate-950 font-sans">
                      Depreciation
                    </td>
                    {projectionResult.projections.map(p => (
                      <td key={p.year} className="py-2.5 px-4 text-right">₹{p.depreciation_cr.toLocaleString('en-IN')}</td>
                    ))}
                  </tr>

                  <tr className="hover:bg-slate-900/50 text-slate-300">
                    <td className="py-2.5 px-4 sticky left-0 bg-slate-950 font-sans">
                      Interest Expense
                    </td>
                    {projectionResult.projections.map(p => (
                      <td key={p.year} className="py-2.5 px-4 text-right">₹{p.interest_cr.toLocaleString('en-IN')}</td>
                    ))}
                  </tr>

                  <tr className="hover:bg-slate-900/50 bg-slate-900/20 font-semibold text-slate-100">
                    <td className="py-2.5 px-4 sticky left-0 bg-slate-900 text-cyan-400 font-sans font-bold">
                      Net Profit (PAT)
                    </td>
                    {projectionResult.projections.map(p => (
                      <td key={p.year} className="py-2.5 px-4 text-right">₹{p.pat_cr.toLocaleString('en-IN')}</td>
                    ))}
                  </tr>

                  <tr className="hover:bg-slate-900/50 text-slate-200 font-bold">
                    <td className="py-2.5 px-4 sticky left-0 bg-slate-950 font-sans text-amber-300">
                      Projected EPS (₹)
                    </td>
                    {projectionResult.projections.map(p => (
                      <td key={p.year} className="py-2.5 px-4 text-right text-amber-300">₹{p.eps}</td>
                    ))}
                  </tr>

                  <tr className="hover:bg-slate-900/50 text-slate-300">
                    <td className="py-2.5 px-4 sticky left-0 bg-slate-950 font-sans">
                      <ConceptHelp term="cfo" label="Cash from Operations (CFO)" />
                    </td>
                    {projectionResult.projections.map(p => (
                      <td key={p.year} className="py-2.5 px-4 text-right">{isFiniteNumber(p.cfo_cr) ? `₹${formatIndianNumber(p.cfo_cr)}` : '—'}</td>
                    ))}
                  </tr>

                  <tr className="hover:bg-slate-900/50 text-slate-300">
                    <td className="py-2.5 px-4 sticky left-0 bg-slate-950 font-sans">
                      <ConceptHelp term="capex" label="Estimated Capex" />
                    </td>
                    {projectionResult.projections.map(p => (
                      <td key={p.year} className="py-2.5 px-4 text-right">{isFiniteNumber(p.capex_cr) ? `₹${formatIndianNumber(p.capex_cr)}` : '—'}</td>
                    ))}
                  </tr>

                  <tr className="hover:bg-slate-900/50 bg-emerald-950/30 text-emerald-300 font-bold">
                    <td className="py-2.5 px-4 sticky left-0 bg-emerald-950/80 font-sans">
                      <ConceptHelp term="fcf" label="Free Cash Flow (FCF)" />
                    </td>
                    {projectionResult.projections.map(p => (
                      <td key={p.year} className="py-2.5 px-4 text-right text-emerald-300">{isFiniteNumber(p.fcf_cr) ? `₹${formatIndianNumber(p.fcf_cr)}` : '—'}</td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          </>}
          </>
        )}
        </div>
      )}

      {/* TAB 2: BUSINESS ANALYSIS */}
      {activeTab === 'outlook' && (
        <BusinessAnalysisView
          stock={stock}
          docIntel={docIntel}
          loadingDocIntel={loadingDocIntel}
          docIntelError={docIntelError}
          generatingDocIntel={generatingDocIntel}
          aiStatus={aiStatus}
          researchStatus={researchStatus}
          filingDiscoveryState={filingDiscoveryState || 'idle'}
          filingDiscoveryRevision={filingDiscoveryRevision}
          onGenerateIntel={handleGenerateIntel}
          onOpenKeyModal={() => { setIsKeyModalOpen(true); setKeySaveMessage(null); }}
        />
      )}

      {/* TAB 3: FINANCIAL STATEMENTS (RAW SCREENER DATA) */}
      {activeTab === 'financials' && (
        <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-xl font-bold text-white">Financial Statements</h3>
                <DataOriginBadge origin="reported_fact" />
                <FinancialColorLegend />
              </div>
              <p className="text-xs text-slate-400">A quick read first, followed by the complete consolidated Screener.in statement</p>
            </div>

            {/* Sub-Tabs for Statements */}
            <div className="flex max-w-full items-center gap-1.5 overflow-x-auto bg-slate-950 p-1 rounded-xl border border-slate-800">
              <button
                onClick={() => setFinancialSubTab('quarters')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  financialSubTab === 'quarters' ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white'
                }`}
              >
                Quarterly Results
              </button>
              <button
                onClick={() => setFinancialSubTab('pl')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  financialSubTab === 'pl' ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white'
                }`}
              >
                Profit & Loss (Annual)
              </button>
              <button
                onClick={() => setFinancialSubTab('balance_sheet')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  financialSubTab === 'balance_sheet' ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white'
                }`}
              >
                Balance Sheet
              </button>
              <button
                onClick={() => setFinancialSubTab('cash_flow')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  financialSubTab === 'cash_flow' ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white'
                }`}
              >
                Cash Flows
              </button>
            </div>
          </div>

          <StatementSummaryStrip items={statementSummary} />

          {/* Render selected statement */}
          {financialSubTab === 'quarters' && <FinancialStatementTable statement={stock.quarters} comparisonLabel="QoQ" />}
          {financialSubTab === 'pl' && <FinancialStatementTable statement={stock.profit_loss} />}
          {financialSubTab === 'balance_sheet' && <FinancialStatementTable statement={stock.balance_sheet} />}
          {financialSubTab === 'cash_flow' && (
            <div className="space-y-6">
              {isFinancialBusiness && (
                <div className="p-4 rounded-2xl bg-sky-950/30 border border-sky-800/40 text-xs text-sky-200 flex items-start gap-3">
                  <Info className="w-4 h-4 text-sky-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <span className="font-semibold text-sky-300">Banking & Financial Business Model Notice:</span>
                    <p className="mt-1 text-slate-300">
                      Conventional CFO/FCF quality analysis is not used for banking businesses because deposit, lending and financial-asset movements dominate operating cash flows. The raw standardized cash flow statement is presented below for source faithfulness.
                    </p>
                  </div>
                </div>
              )}

              <FinancialStatementTable statement={stock.cash_flow} />

              {/* Free Cash Flow Reconciliation & Capex Methodology Breakdown (General Corporate only) */}
              {!isFinancialBusiness && stock.analytics?.cash_flow_quality?.fcf_trends && stock.analytics.cash_flow_quality.fcf_trends.length > 0 && (
                <details className="advanced-details">
                  <summary>
                    <div>
                      <h4 className="text-sm font-bold text-white flex items-center gap-2">
                        <TrendingUp className="w-4 h-4 text-emerald-400" />
                        <ConceptHelp term="fcf" label="Deterministic Free Cash Flow Breakdown" onCalculationDetails={() => setSelectedFormulaKey('free_cash_flow')} />
                        <DataOriginBadge origin="stocker_calculation" />
                      </h4>
                      <p className="text-xs text-slate-400">
                        Expand the reported inputs, backend formula output, and capex methodology.
                      </p>
                    </div>
                    <ChevronDown className="advanced-details-chevron" />
                  </summary>

                  <div className="advanced-details-body space-y-4">
                    <div className="flex justify-end">
                    <button
                      onClick={() => setSelectedFormulaKey('free_cash_flow')}
                      className="text-xs font-semibold text-cyan-400 hover:underline flex items-center gap-1 bg-cyan-950/40 px-3 py-1.5 rounded-xl border border-cyan-800/40 self-start sm:self-auto"
                    >
                      <Info className="w-3.5 h-3.5" />
                      <span>Formula & Inputs</span>
                    </button>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left border-collapse font-mono">
                      <thead>
                        <tr className="border-b border-slate-800 text-[11px] text-slate-400">
                          <th className="py-2.5 px-3 font-semibold">Period</th>
                          <th className="py-2.5 px-3 font-semibold text-right text-cyan-400"><ConceptHelp term="cfo" label="Reported CFO (₹ Cr)" /></th>
                          <th className="py-2.5 px-3 font-semibold text-right text-slate-300">Reported PAT (₹ Cr)</th>
                          <th className="py-2.5 px-3 font-semibold text-right text-amber-400"><ConceptHelp term="capex" label="Capex (₹ Cr)" /></th>
                          <th className="py-2.5 px-3 font-semibold text-right text-emerald-400"><ConceptHelp term="fcf" label="Stocker FCF (₹ Cr)" /></th>
                          <th className="py-2.5 px-3 font-semibold text-right text-slate-300"><ConceptHelp term="cfo_pat" label="CFO / PAT %" /></th>
                          <th className="py-2.5 px-3 font-semibold text-slate-400">Capex Methodology</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {stock.analytics.cash_flow_quality.fcf_trends.map((row, idx) => (
                          <tr key={idx} className="hover:bg-slate-900/50 transition-colors">
                            <td className="py-2.5 px-3 font-bold text-slate-200">{row.period}</td>
                            <td className="py-2.5 px-3 text-right text-cyan-300 font-bold">
                              {isFiniteNumber(row.reported_cfo_cr) ? row.reported_cfo_cr.toLocaleString('en-IN') : '—'}
                            </td>
                            <td className="py-2.5 px-3 text-right text-slate-300">
                              {isFiniteNumber(row.reported_pat_cr) ? row.reported_pat_cr.toLocaleString('en-IN') : '—'}
                            </td>
                            <td className="py-2.5 px-3 text-right text-amber-300">
                              {isFiniteNumber(row.capex_cr) ? row.capex_cr.toLocaleString('en-IN') : '—'}
                            </td>
                            <td className={`py-2.5 px-3 text-right font-bold ${
                              !isFiniteNumber(row.stocker_derived_fcf_cr) ? 'text-slate-400' : row.stocker_derived_fcf_cr >= 0 ? 'text-emerald-400' : 'text-rose-400'
                            }`}>
                              {isFiniteNumber(row.stocker_derived_fcf_cr) ? row.stocker_derived_fcf_cr.toLocaleString('en-IN') : '—'}
                            </td>
                            <td className="py-2.5 px-3 text-right text-slate-300">
                              {formatPercent(row.cfo_to_pat_pct)}
                            </td>
                            <td className="py-2.5 px-3 text-slate-400 text-[11px] font-sans">
                              <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
                                {row.capex_methodology || 'Derived'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  </div>
                </details>
              )}
            </div>
          )}
        </div>
      )}

      {/* TAB 4: TREND ANALYTICS & VISUALIZATIONS */}
      {activeTab === 'charts' && (
        <div className="space-y-6">
          {isBank ? (
            <div className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Bank Chart 1: Revenue & Net Profit (PAT) Trajectory */}
                <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
                  <div>
                    <h4 className="font-bold text-white text-sm">Quarterly Revenue & Net Profit Trajectory</h4>
                    <p className="text-xs text-slate-400">Total revenue / financing income and bottom-line PAT trend</p>
                  </div>
                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={quarterlyTrends}>
                        <defs>
                          <linearGradient id="colorSalesBank" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#0284c7" stopOpacity={0.4}/>
                            <stop offset="95%" stopColor="#0284c7" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                        <XAxis dataKey="period" stroke="var(--chart-axis)" fontSize={10} />
                        <YAxis yAxisId="left" stroke="#0284c7" fontSize={10} tickFormatter={formatCompactCrores} width={58} />
                        <YAxis yAxisId="right" orientation="right" stroke="#10b981" fontSize={10} tickFormatter={formatCompactCrores} width={58} />
                        {latestQuarterTrend?.period && <ReferenceLine x={latestQuarterTrend.period} stroke="var(--border-strong)" strokeDasharray="4 4" label={{ value: 'Latest', fill: 'var(--text-muted)', fontSize: 10 }} />}
                        <Tooltip 
                          contentStyle={{ backgroundColor: 'var(--card-bg)', borderColor: 'var(--border-strong)', color: 'var(--text-primary)', borderRadius: '12px' }}
                          labelStyle={{ color: 'var(--text-primary)', fontWeight: 700 }}
                          cursor={{ fill: 'var(--hover-bg)' }}
                          formatter={(val: any, name: string) => [
                            isFiniteNumber(val) ? `₹${val.toLocaleString('en-IN')} Cr` : 'Unavailable',
                            name
                          ]}
                        />
                        <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                        <Area yAxisId="left" type="monotone" dataKey="sales" name="Total Revenue (₹ Cr)" stroke="#0284c7" fillOpacity={1} fill="url(#colorSalesBank)" />
                        <Line yAxisId="right" type="monotone" dataKey="pat" name="Net Profit PAT (₹ Cr)" stroke="#10b981" strokeWidth={2.5} dot={{ r: 3 }} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Bank Chart 2: Deposits vs Advances vs Borrowings */}
                <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
                  <div>
                    <h4 className="font-bold text-white text-sm">Banking Balance Sheet: Funding & Advances</h4>
                    <p className="text-xs text-slate-400">Deposit mobilization vs loan book expansion and wholesale borrowings</p>
                  </div>
                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={bankFundingChartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                        <XAxis dataKey="period" stroke="var(--chart-axis)" fontSize={10} />
                        <YAxis stroke="var(--chart-axis)" fontSize={10} tickFormatter={formatCompactCrores} width={58} />
                        <Tooltip 
                          contentStyle={{ backgroundColor: 'var(--card-bg)', borderColor: 'var(--border-strong)', color: 'var(--text-primary)', borderRadius: '12px' }}
                          labelStyle={{ color: 'var(--text-primary)', fontWeight: 700 }}
                          cursor={{ fill: 'var(--hover-bg)' }}
                          formatter={(val: any, name: string) => [isFiniteNumber(val) ? `₹${val.toLocaleString('en-IN')} Cr` : 'Unavailable', name]}
                        />
                        <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                        <Bar dataKey="deposits_cr" name="Deposits (₹ Cr)" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="advances_cr" name="Advances (₹ Cr)" fill="#10b981" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="borrowings_cr" name="Borrowings (₹ Cr)" fill="#64748b" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>

              {/* Bank Chart 3: Asset Quality: Gross NPA % vs Net NPA % */}
              {hasNpaData ? (
                <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
                  <div>
                    <h4 className="font-bold text-white text-sm">Asset Quality: Gross NPA % vs Net NPA % Trajectory</h4>
                    <p className="text-xs text-slate-400">Tracking non-performing assets and provisioning buffer health</p>
                  </div>
                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={bankNpaChartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                        <XAxis dataKey="period" stroke="var(--chart-axis)" fontSize={10} />
                        <YAxis stroke="var(--chart-axis)" fontSize={10} tickFormatter={(v) => `${v}%`} width={48} />
                        <Tooltip 
                          contentStyle={{ backgroundColor: 'var(--card-bg)', borderColor: 'var(--border-strong)', color: 'var(--text-primary)', borderRadius: '12px' }}
                          labelStyle={{ color: 'var(--text-primary)', fontWeight: 700 }}
                          cursor={{ fill: 'var(--hover-bg)' }}
                          formatter={(val: any, name: string) => [isFiniteNumber(val) ? `${val}%` : 'Unavailable', name]}
                        />
                        <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                        <Line type="monotone" dataKey="gross_npa_pct" name="Gross NPA %" stroke="#f59e0b" strokeWidth={2.5} dot={{ r: 3 }} />
                        <Line type="monotone" dataKey="net_npa_pct" name="Net NPA %" stroke="#ef4444" strokeWidth={2.5} dot={{ r: 3 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded-2xl bg-slate-900/50 border border-slate-800 text-xs text-slate-400">
                  <span className="font-semibold text-slate-300">Asset Quality Note:</span> Gross NPA and Net NPA trajectory data is not available in the current source tables for this institution.
                </div>
              )}
            </div>
          ) : isFinancialBusiness ? (
            <div className="space-y-6">
              <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
                <div>
                  <h4 className="font-bold text-white text-sm">Quarterly Revenue Trajectory</h4>
                  <p className="text-xs text-slate-400">Reported topline progression</p>
                </div>
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={quarterlyTrends}>
                      <defs>
                        <linearGradient id="colorSalesFin" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.4}/>
                          <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                      <XAxis dataKey="period" stroke="var(--chart-axis)" fontSize={10} />
                      <YAxis stroke="#0ea5e9" fontSize={10} tickFormatter={formatCompactCrores} width={58} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: 'var(--card-bg)', borderColor: 'var(--border-strong)', color: 'var(--text-primary)', borderRadius: '12px' }}
                        labelStyle={{ color: 'var(--text-primary)', fontWeight: 700 }}
                        cursor={{ fill: 'var(--hover-bg)' }}
                        formatter={(val: any, name: string) => [isFiniteNumber(val) ? `₹${val.toLocaleString('en-IN')} Cr` : 'Unavailable', name]}
                      />
                      <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                      <Area type="monotone" dataKey="sales" name="Revenue (₹ Cr)" stroke="#0ea5e9" fillOpacity={1} fill="url(#colorSalesFin)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-sky-950/30 border border-sky-800/40 text-xs text-sky-200">
                <span className="font-semibold text-sky-300">Financial Sector Notice:</span> Conventional industrial charts (Earnings Quality CFO/FCF and Balance Sheet CWIP triggers) are omitted because this entity operates under a financial business model. Specialized metrics for this sub-sector will be introduced in a future phase.
              </div>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                
                {/* Chart 1: Quarterly Sales & Operating Profit Trend */}
                <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
                  <div>
                    <h4 className="font-bold text-white text-sm"><ConceptHelp term="opm" label="Quarterly Revenue & OPM % Trajectory" /></h4>
                    <p className="text-xs text-slate-400"><ConceptHelp term="qoq" label="Quarter-on-quarter momentum" /> and margin expansion</p>
                  </div>
                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={quarterlyTrends}>
                        <defs>
                          <linearGradient id="colorSales" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#10b981" stopOpacity={0.4}/>
                            <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                        <XAxis dataKey="period" stroke="var(--chart-axis)" fontSize={10} />
                        <YAxis yAxisId="left" stroke="#10b981" fontSize={10} tickFormatter={formatCompactCrores} width={58} />
                        <YAxis yAxisId="right" orientation="right" stroke="#06b6d4" fontSize={10} tickFormatter={(value) => `${value}%`} width={42} />
                        {latestQuarterTrend?.period && <ReferenceLine x={latestQuarterTrend.period} stroke="var(--border-strong)" strokeDasharray="4 4" label={{ value: 'Latest', fill: 'var(--text-muted)', fontSize: 10 }} />}
                        <Tooltip 
                          contentStyle={{ backgroundColor: 'var(--card-bg)', borderColor: 'var(--border-strong)', color: 'var(--text-primary)', borderRadius: '12px' }}
                          labelStyle={{ color: 'var(--text-primary)', fontWeight: 700 }}
                          cursor={{ fill: 'var(--hover-bg)' }}
                          formatter={(val: any, name: string) => [
                            isFiniteNumber(val) ? (name.includes('OPM') ? `${val}%` : `₹${val.toLocaleString('en-IN')} Cr`) : 'Unavailable',
                            name
                          ]}
                        />
                        <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                        <Area yAxisId="left" type="monotone" dataKey="sales" name="Sales (₹ Cr)" stroke="#10b981" fillOpacity={1} fill="url(#colorSales)" />
                        <Line yAxisId="right" type="monotone" dataKey="opm_pct" name="OPM %" stroke="#06b6d4" strokeWidth={2.5} dot={{ r: 3 }} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Chart 2: Earnings Quality: Net Profit vs CFO vs FCF */}
                <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
                  <div>
                    <h4 className="font-bold text-white text-sm">Earnings Quality: Net Profit vs <ConceptHelp term="cfo" label="CFO" /> vs <ConceptHelp term="fcf" label="Free Cash Flow" /></h4>
                    <p className="text-xs text-slate-400">Validating whether accounting profits convert into hard operational cash</p>
                  </div>
                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={fcfChartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                        <XAxis dataKey="period" stroke="var(--chart-axis)" fontSize={10} />
                        <YAxis stroke="var(--chart-axis)" fontSize={10} tickFormatter={formatCompactCrores} width={58} />
                        {latestFcfTrend?.period && <ReferenceLine x={latestFcfTrend.period} stroke="var(--border-strong)" strokeDasharray="4 4" label={{ value: 'Latest', fill: 'var(--text-muted)', fontSize: 10 }} />}
                        <ReferenceLine y={0} stroke="var(--border-strong)" />
                        <Tooltip 
                          contentStyle={{ backgroundColor: 'var(--card-bg)', borderColor: 'var(--border-strong)', color: 'var(--text-primary)', borderRadius: '12px' }}
                          labelStyle={{ color: 'var(--text-primary)', fontWeight: 700 }}
                          cursor={{ fill: 'var(--hover-bg)' }}
                          formatter={(val: any) => [isFiniteNumber(val) ? `₹${val.toLocaleString('en-IN')} Cr` : 'Unavailable']}
                        />
                        <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                        <Bar dataKey="pat_cr" name="Net Profit (PAT)" fill="#64748b" radius={[4, 4, 0, 0]}>
                          {fcfChartData.map((entry, index) => <Cell key={`pat-${index}`} fill={(entry.pat_cr ?? 0) < 0 ? '#fb7185' : '#64748b'} />)}
                        </Bar>
                        <Bar dataKey="cfo_cr" name="Cash from Operations (CFO)" fill="#06b6d4" radius={[4, 4, 0, 0]}>
                          {fcfChartData.map((entry, index) => <Cell key={`cfo-${index}`} fill={(entry.cfo_cr ?? 0) < 0 ? '#fb7185' : '#06b6d4'} />)}
                        </Bar>
                        <Bar dataKey="fcf_cr" name="Free Cash Flow (FCF)" fill="#10b981" radius={[4, 4, 0, 0]}>
                          {fcfChartData.map((entry, index) => <Cell key={`fcf-${index}`} fill={(entry.fcf_cr ?? 0) < 0 ? '#fb7185' : '#10b981'} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

              </div>

              {/* Chart 3: Balance Sheet & CWIP Growth Trigger */}
              <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
                <div>
                  <h4 className="font-bold text-white text-sm"><ConceptHelp term="cwip" label="Balance Sheet Capital Allocation & CWIP Trigger" /></h4>
                  <p className="text-xs text-slate-400">Capital Work in Progress (CWIP) as % of Net Block signals upcoming revenue capacity</p>
                </div>
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={bsTrends}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                      <XAxis dataKey="period" stroke="var(--chart-axis)" fontSize={10} />
                      <YAxis yAxisId="left" stroke="var(--chart-axis)" fontSize={10} tickFormatter={formatCompactCrores} width={58} />
                      <YAxis yAxisId="right" orientation="right" stroke="#f59e0b" fontSize={10} tickFormatter={(value) => `${value}%`} width={42} />
                      {latestBsTrend?.period && <ReferenceLine x={latestBsTrend.period} stroke="var(--border-strong)" strokeDasharray="4 4" label={{ value: 'Latest', fill: 'var(--text-muted)', fontSize: 10 }} />}
                      <Tooltip 
                        contentStyle={{ backgroundColor: 'var(--card-bg)', borderColor: 'var(--border-strong)', color: 'var(--text-primary)', borderRadius: '12px' }}
                        labelStyle={{ color: 'var(--text-primary)', fontWeight: 700 }}
                        cursor={{ fill: 'var(--hover-bg)' }}
                        formatter={(value: any, name: string) => [
                          isFiniteNumber(value) ? name.includes('%') ? `${value}%` : `₹${value.toLocaleString('en-IN')} Cr` : 'Unavailable',
                          name
                        ]}
                      />
                      <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                      <Bar yAxisId="left" dataKey="fixed_assets_cr" name="Fixed Assets (₹ Cr)" fill="var(--chart-axis)" radius={[4, 4, 0, 0]} />
                      <Bar yAxisId="left" dataKey="cwip_cr" name="CWIP (₹ Cr)" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                      <Line yAxisId="right" type="monotone" dataKey="cwip_to_fixed_assets_pct" name="CWIP / Net Block %" stroke="#10b981" strokeWidth={2} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* TAB 5: 5-PILLAR SCORECARD & RISKS */}
      {activeTab === 'scorecard' && (
        <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-8">
          {lifecycleStatusPending && (
            <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
              <p className="text-xs font-bold text-slate-200">Research classification pending</p>
              <p className="text-[11px] text-slate-400 mt-1">Showing the latest stored quantitative score without implying a completed research-confidence classification.</p>
            </div>
          )}
          {researchStatus && (
            <div className={`rounded-2xl border p-4 ${researchStatus.investment_score === 'evidence_enriched' ? 'bg-cyan-950/30 border-cyan-800/50' : 'bg-amber-950/20 border-amber-800/40'}`}>
              <p className="text-xs font-bold text-slate-100">
                {researchStatus.investment_score === 'provisional' ? 'Provisional — financial analysis only' : researchStatus.investment_score === 'evidence_enriched' ? 'Evidence-enriched' : researchStatus.investment_score === 'incomplete' ? 'Incomplete research' : 'Not available'}
              </p>
              <p className="text-[11px] text-slate-400 mt-1">Investment attractiveness is separate from research confidence. Complete filing and business analysis for a fully researched view.</p>
            </div>
          )}
          {!investmentScoreUnavailable && <>
          
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h3 className="text-xl font-bold text-white">5-Pillar Fundamental Scorecard</h3>
              <p className="text-xs text-slate-400">Quantitative multi-factor weighting model</p>
            </div>
            <div className="text-right">
              <span className="text-xs text-slate-400 font-mono">Composite Verdict</span>
              <div className="text-lg font-extrabold text-emerald-400">{researchStatus ? stock.score.verdict : 'Classification pending'}</div>
            </div>
          </div>

          {/* 5 Pillar Bars */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            
            <div className="bg-slate-950/70 p-4 rounded-2xl border border-slate-800 space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Growth Momentum</span>
                <span className="font-mono font-bold text-slate-200">{stock.score.growth_momentum_score}/100</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div className="bg-emerald-500 h-full rounded-full" style={{ width: `${stock.score.growth_momentum_score}%` }} />
              </div>
              <span className="text-[10px] text-slate-500 font-mono">Weight: 20%</span>
            </div>

            <div className="bg-slate-950/70 p-4 rounded-2xl border border-slate-800 space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Cash Flow Quality</span>
                <span className="font-mono font-bold text-emerald-400">{stock.score.cash_quality_fcf_score}/100</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div className="bg-teal-500 h-full rounded-full" style={{ width: `${stock.score.cash_quality_fcf_score}%` }} />
              </div>
              <span className="text-[10px] text-slate-500 font-mono">Weight: 25%</span>
            </div>

            <div className="bg-slate-950/70 p-4 rounded-2xl border border-slate-800 space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Capital Efficiency</span>
                <span className="font-mono font-bold text-cyan-400">{stock.score.capital_efficiency_score}/100</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div className="bg-cyan-500 h-full rounded-full" style={{ width: `${stock.score.capital_efficiency_score}%` }} />
              </div>
              <span className="text-[10px] text-slate-500 font-mono">Weight: 20%</span>
            </div>

            <div className="bg-slate-950/70 p-4 rounded-2xl border border-slate-800 space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Balance Sheet Safety</span>
                <span className="font-mono font-bold text-slate-200">{stock.score.balance_sheet_safety_score}/100</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div className="bg-indigo-500 h-full rounded-full" style={{ width: `${stock.score.balance_sheet_safety_score}%` }} />
              </div>
              <span className="text-[10px] text-slate-500 font-mono">Weight: 15%</span>
            </div>

            <div className="bg-slate-950/70 p-4 rounded-2xl border border-slate-800 space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Valuation Headroom</span>
                <span className="font-mono font-bold text-amber-400">{stock.score.valuation_margin_score}/100</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div className="bg-amber-500 h-full rounded-full" style={{ width: `${stock.score.valuation_margin_score}%` }} />
              </div>
              <span className="text-[10px] text-slate-500 font-mono">Weight: 20%</span>
            </div>

          </div>

          {/* Investment Thesis Box */}
          <div className="bg-slate-900/60 p-6 rounded-2xl border border-slate-800 space-y-2">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 block">
              Automated Investment Thesis
            </span>
            <p className="text-sm text-slate-200 leading-relaxed">
              {stock.score.investment_thesis}
            </p>
          </div>

          {/* Catalysts vs Risks */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            <div className="bg-emerald-950/20 p-5 rounded-2xl border border-emerald-800/30 space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4" />
                Key Investment Catalysts
              </span>
              <ul className="space-y-2">
                {stock.score.key_catalysts.map((c, i) => (
                  <li key={i} className="text-xs text-slate-300 flex items-start gap-2 leading-relaxed">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5 shrink-0" />
                    <span>{c}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="bg-rose-950/20 p-5 rounded-2xl border border-rose-800/30 space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-rose-400 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4" />
                Key Investment Risks
              </span>
              <ul className="space-y-2">
                {stock.score.key_risks.map((r, i) => (
                  <li key={i} className="text-xs text-slate-300 flex items-start gap-2 leading-relaxed">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-400 mt-1.5 shrink-0" />
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>

          </div>
          </>}
        </div>
      )}



      {/* Live Pipeline Execution Progress Modal */}
      {generatingDocIntel && (
        <div className="fixed inset-0 bg-slate-950/85 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-3xl p-6 md:p-8 max-w-lg w-full space-y-6 shadow-2xl animate-in fade-in zoom-in duration-200">
            <div className="flex items-center gap-3.5">
              <div className="w-11 h-11 rounded-2xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30 shrink-0">
                <Sparkles className="w-6 h-6 animate-pulse text-emerald-400" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Running Live AI Analysis</h3>
                <p className="text-xs text-slate-400">Scanning source documents for {stock.name} ({stock.symbol})</p>
              </div>
            </div>

            {/* Step-by-Step Pipeline Progress */}
            <div className="space-y-3 bg-slate-950/70 p-4 rounded-2xl border border-slate-800">
              <div className="flex items-center gap-3 text-xs">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] ${
                  generationStep >= 1 ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-400'
                }`}>
                  {generationStep > 1 ? '✓' : '1'}
                </div>
                <div className="flex-1">
                  <p className={`font-semibold ${generationStep >= 1 ? 'text-slate-200' : 'text-slate-500'}`}>
                    Discovering Verified Filings
                  </p>
                  <p className="text-[11px] text-slate-500">Screener.in + BSE India + NSE India feeds</p>
                </div>
                {generationStep === 1 && <RefreshCw className="w-3.5 h-3.5 text-emerald-400 animate-spin" />}
              </div>

              <div className="flex items-center gap-3 text-xs">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] ${
                  generationStep >= 2 ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-400'
                }`}>
                  {generationStep > 2 ? '✓' : '2'}
                </div>
                <div className="flex-1">
                  <p className={`font-semibold ${generationStep >= 2 ? 'text-slate-200' : 'text-slate-500'}`}>
                    Reading Source PDFs
                  </p>
                  <p className="text-[11px] text-slate-500">Extracting page-by-page text & table markers</p>
                </div>
                {generationStep === 2 && <RefreshCw className="w-3.5 h-3.5 text-emerald-400 animate-spin" />}
              </div>

              <div className="flex items-center gap-3 text-xs">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] ${
                  generationStep >= 3 ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-400'
                }`}>
                  {generationStep > 3 ? '✓' : '3'}
                </div>
                <div className="flex-1">
                  <p className={`font-semibold ${generationStep >= 3 ? 'text-slate-200' : 'text-slate-500'}`}>
                    Gemini 2.0 Institutional Extraction
                  </p>
                  <p className="text-[11px] text-slate-500">Promise vs Delivery, Growth Drivers & Risks</p>
                </div>
                {generationStep === 3 && <RefreshCw className="w-3.5 h-3.5 text-emerald-400 animate-spin" />}
              </div>

              <div className="flex items-center gap-3 text-xs">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] ${
                  generationStep >= 4 ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-400'
                }`}>
                  {generationStep >= 4 ? '✓' : '4'}
                </div>
                <div className="flex-1">
                  <p className={`font-semibold ${generationStep >= 4 ? 'text-slate-200' : 'text-slate-500'}`}>
                    Fact Grounding & Citation Audit
                  </p>
                  <p className="text-[11px] text-slate-500">Linking quotes to exact source pages</p>
                </div>
                {generationStep >= 4 && <Check className="w-3.5 h-3.5 text-emerald-400" />}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* API Key Configuration Modal */}
      {isKeyModalOpen && (
        <div className="fixed inset-0 bg-slate-950/85 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-3xl p-6 md:p-8 max-w-md w-full space-y-5 shadow-2xl animate-in fade-in zoom-in duration-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-2xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30">
                  <KeyRound className="w-4 h-4 text-emerald-400" />
                </div>
                <div>
                  <h3 className="font-bold text-white text-sm">Configure Gemini AI Key</h3>
                  <p className="text-[11px] text-slate-400">Institutional Document Intelligence</p>
                </div>
              </div>
              <button 
                onClick={() => { setIsKeyModalOpen(false); setKeySaveMessage(null); }}
                className="text-slate-400 hover:text-white text-xs p-1 rounded-lg hover:bg-slate-800"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Stocker extracts facts directly from original BSE/NSE filings using <strong>Google Gemini 2.0 Flash</strong>. Enter your free API key below:
            </p>

            {aiStatus?.configured && (
              <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-xs flex items-center justify-between">
                <span className="text-slate-400">Current Key:</span>
                <code className="text-emerald-400 font-mono">{aiStatus.key_preview}</code>
              </div>
            )}

            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300 block">
                Gemini API Key (starts with <code className="text-emerald-400">AIzaSy...</code>):
              </label>
              <input
                type="password"
                placeholder="AIzaSy..."
                value={inputKey}
                onChange={(e) => setInputKey(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-emerald-500 font-mono"
              />
            </div>

            {keySaveMessage && (
              <div className={`p-3 rounded-xl text-xs border ${
                keySaveMessage.type === 'success' 
                  ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300'
                  : 'bg-rose-950/40 border-rose-800 text-rose-300'
              }`}>
                {keySaveMessage.text}
              </div>
            )}

            <div className="flex items-center gap-2 pt-2">
              <button
                onClick={handleSaveKey}
                disabled={savingKey}
                className="flex-1 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 text-slate-950 font-bold text-xs rounded-xl transition-colors flex items-center justify-center gap-1.5"
              >
                {savingKey ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                <span>{savingKey ? 'Verifying Key...' : 'Save & Verify Key'}</span>
              </button>
              <a
                href="https://aistudio.google.com/app/apikey"
                target="_blank"
                rel="noreferrer"
                className="py-2.5 px-3 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold text-xs rounded-xl border border-slate-700 flex items-center gap-1"
              >
                <span>Get Free Key</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Uses the backend-provided formula, inputs, source, and explanation verbatim. */}
      <FormulaTransparencyModal item={selectedFormula} onClose={() => setSelectedFormulaKey(null)} />

    </div>
  );
};
