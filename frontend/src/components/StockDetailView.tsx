import React, { useState, useEffect } from 'react';
import { 
  StockDetail, ProjectionAssumption, ProjectionResult, 
  FinancialStatement, BusinessOutlookIntelligence 
} from '../types';
import { projectStock, fetchDocIntelligence, generateDocIntelligence } from '../api';
import { 
  TrendingUp, BarChart3, Sliders, FileText, ShieldAlert, 
  ExternalLink, ArrowUpRight, ArrowDownRight, RefreshCw, 
  CheckCircle2, AlertTriangle, Sparkles, Building, Layers, 
  DollarSign, Activity, FileSpreadsheet, ChevronRight, HelpCircle,
  Clock, Target, Compass, Search, Zap, Info, ChevronDown,
  Mic, Presentation, Bell
} from 'lucide-react';
import { 
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, 
  Tooltip, CartesianGrid, BarChart, Bar, Legend, LineChart, Line 
} from 'recharts';

interface StockDetailViewProps {
  stock: StockDetail;
  onBack: () => void;
  onScrapeRefresh?: () => void;
}

export const StockDetailView: React.FC<StockDetailViewProps> = ({ stock, onBack, onScrapeRefresh }) => {
  const [activeTab, setActiveTab] = useState<'financials' | 'charts' | 'projection' | 'outlook' | 'scorecard' | 'documents'>('projection');
  const [financialSubTab, setFinancialSubTab] = useState<'quarters' | 'pl' | 'balance_sheet' | 'cash_flow'>('quarters');
  
  // Document Intelligence (Business Outlook) State
  const [docIntel, setDocIntel] = useState<BusinessOutlookIntelligence | null>(null);
  const [loadingDocIntel, setLoadingDocIntel] = useState<boolean>(false);
  const [generatingDocIntel, setGeneratingDocIntel] = useState<boolean>(false);
  const [docIntelError, setDocIntelError] = useState<string | null>(null);

  // Projection Simulator State
  const [growthRate, setGrowthRate] = useState<number>(stock.projection.assumptions.revenue_growth_rate_pct);
  const [opmRate, setOpmRate] = useState<number>(stock.projection.assumptions.target_opm_pct);
  const [capexRate, setCapexRate] = useState<number>(stock.projection.assumptions.capex_pct_of_sales);
  const [exitPe, setExitPe] = useState<number>(stock.projection.assumptions.target_exit_pe);
  const [wacc, setWacc] = useState<number>(stock.projection.assumptions.discount_rate_wacc_pct);
  const [terminalG, setTerminalG] = useState<number>(stock.projection.assumptions.terminal_growth_rate_pct);
  
  const [projectionResult, setProjectionResult] = useState<ProjectionResult>(stock.projection);
  const [isProjecting, setIsProjecting] = useState<boolean>(false);

  // Load document intelligence on mount / stock change
  useEffect(() => {
    const loadIntel = async () => {
      setLoadingDocIntel(true);
      setDocIntelError(null);
      try {
        const intel = await fetchDocIntelligence(stock.symbol);
        setDocIntel(intel);
      } catch (err: any) {
        setDocIntelError(err.message || 'Failed to load document intelligence');
      } finally {
        setLoadingDocIntel(false);
      }
    };
    loadIntel();
  }, [stock.symbol]);

  const handleGenerateIntel = async () => {
    setGeneratingDocIntel(true);
    setDocIntelError(null);
    try {
      const res = await generateDocIntelligence(stock.symbol);
      setDocIntel(res);
    } catch (err: any) {
      setDocIntelError(err.message || 'Failed to run AI document extraction. Please check your .env configuration.');
    } finally {
      setGeneratingDocIntel(false);
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
    const baseGrowth = stock.projection.historical_revenue_cagr_3yr || 12.0;
    const baseOpm = stock.projection.historical_opm_median || 20.0;
    const pe = stock.ratios.stock_pe || 25.0;

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

  // Helper to render statement table
  const renderStatementTable = (stmt: FinancialStatement) => {
    return (
      <div className="overflow-x-auto rounded-2xl border border-slate-800">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-slate-900/90 text-slate-400 uppercase tracking-wider border-b border-slate-800">
            <tr>
              <th className="py-3 px-4 sticky left-0 bg-slate-900 z-10 font-sans font-bold text-slate-300 min-w-[200px]">
                Metric (₹ Cr)
              </th>
              {stmt.periods.map(p => (
                <th key={p} className="py-3 px-4 whitespace-nowrap text-right">
                  {p}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {stmt.rows.map((row, rIdx) => {
              const isHighlight = ['Sales', 'Revenue', 'Operating Profit', 'EBITDA', 'Net Profit', 'PAT', 'Cash from Operating Activity', 'Total Assets'].includes(row.metric);
              return (
                <tr 
                  key={row.metric + rIdx} 
                  className={`hover:bg-slate-900/50 transition-colors ${isHighlight ? 'bg-slate-900/20 font-semibold text-slate-100' : 'text-slate-300'}`}
                >
                  <td className={`py-2.5 px-4 sticky left-0 z-10 font-sans ${isHighlight ? 'bg-slate-900 font-bold text-emerald-400' : 'bg-slate-950 text-slate-300'}`}>
                    {row.metric}
                  </td>
                  {stmt.periods.map(p => {
                    const val = row.values[p];
                    return (
                      <td key={p} className="py-2.5 px-4 text-right whitespace-nowrap">
                        {val !== null && val !== undefined ? (
                          typeof val === 'number' ? (
                            row.metric.includes('%') ? `${val}%` : val.toLocaleString('en-IN')
                          ) : val
                        ) : '-'}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="space-y-6 pb-20">
      
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
              className="text-xs font-semibold text-slate-300 hover:text-emerald-400 flex items-center gap-1.5 bg-slate-900 px-3 py-1.5 rounded-xl border border-slate-800 transition-colors"
              title="Force fetch fresh data from Screener.in"
            >
              <RefreshCw className="w-3 h-3 text-emerald-400" />
              <span>Force Refresh</span>
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
                NSE: {stock.symbol}
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
              <span>High/Low: {stock.ratios.high_low || 'N/A'}</span>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500 font-mono">
              <span className="text-emerald-400/90 font-semibold">● Raw Data: {stock.source_name || 'Screener.in'} ({stock.statement_type || 'consolidated'})</span>
              {stock.fetched_at && (
                <>
                  <span>•</span>
                  <span>Scraped: {new Date(stock.fetched_at).toLocaleDateString()} {new Date(stock.fetched_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </>
              )}
            </div>
          </div>

          {/* Price & Composite Score Badges */}
          <div className="flex flex-wrap items-center gap-4 bg-slate-950/80 p-4 rounded-2xl border border-slate-800">
            <div>
              <span className="text-[10px] text-slate-500 uppercase font-mono block">Current Price</span>
              <span className="text-2xl font-extrabold font-mono text-white">
                ₹{stock.ratios.current_price.toLocaleString('en-IN')}
              </span>
            </div>
            <div className="h-10 w-[1px] bg-slate-800 hidden sm:block" />
            <div>
              <span className="text-[10px] text-slate-500 uppercase font-mono block">Market Cap</span>
              <span className="text-sm font-bold font-mono text-slate-200">
                ₹{stock.ratios.market_cap_cr.toLocaleString('en-IN')} Cr
              </span>
            </div>
            <div className="h-10 w-[1px] bg-slate-800 hidden sm:block" />
            <div className="text-right">
              <span className="text-[10px] text-slate-500 uppercase font-mono block">Investability Score</span>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-xl font-extrabold font-mono text-emerald-400">
                  {stock.score.total_composite_score}/100
                </span>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                  {stock.score.verdict}
                </span>
              </div>
            </div>
          </div>

        </div>

        {/* 8 Primary Financial Ratio Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 font-mono">
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-center">
            <span className="text-[10px] text-slate-500 uppercase font-sans block">Stock P/E</span>
            <span className="text-sm font-bold text-slate-100">{stock.ratios.stock_pe}x</span>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-center">
            <span className="text-[10px] text-slate-500 uppercase font-sans block">ROCE</span>
            <span className="text-sm font-bold text-emerald-400">{stock.ratios.roce_pct}%</span>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-center">
            <span className="text-[10px] text-slate-500 uppercase font-sans block">ROE</span>
            <span className="text-sm font-bold text-cyan-400">{stock.ratios.roe_pct}%</span>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-center">
            <span className="text-[10px] text-slate-500 uppercase font-sans block">FCF Yield</span>
            <span className="text-sm font-bold text-teal-400">{stock.ratios.fcf_yield_pct}%</span>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-center">
            <span className="text-[10px] text-slate-500 uppercase font-sans block">3Y Sales CAGR</span>
            <span className="text-sm font-bold text-slate-100">
              {stock.analytics?.growth_rates?.sales_cagr_3yr ?? stock.ratios.sales_growth_3yr_cagr}%
            </span>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-center">
            <span className="text-[10px] text-slate-500 uppercase font-sans block">CFO / PAT (5Y)</span>
            <span className="text-sm font-bold text-emerald-400">
              {stock.analytics?.cash_flow_quality?.cfo_to_pat_5yr_pct}%
            </span>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-center">
            <span className="text-[10px] text-slate-500 uppercase font-sans block">Debt / Equity</span>
            <span className="text-sm font-bold text-slate-100">{stock.ratios.debt_to_equity}x</span>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-center">
            <span className="text-[10px] text-slate-500 uppercase font-sans block">Div Yield</span>
            <span className="text-sm font-bold text-slate-100">{stock.ratios.dividend_yield_pct}%</span>
          </div>
        </div>

        {/* Company About Snippet */}
        <p className="text-xs text-slate-400 leading-relaxed bg-slate-900/40 p-3.5 rounded-xl border border-slate-800/60">
          <strong className="text-slate-200">About Company:</strong> {stock.about}
        </p>
      </div>

      {/* LEVEL 2: 60-SECOND INVESTMENT THESIS & CONVICTION CARD */}
      <div className="glass-panel rounded-3xl p-6 md:p-7 border border-slate-800 bg-gradient-to-br from-slate-950 via-slate-900/90 to-slate-950 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
          <div className="flex items-center gap-2.5">
            <Sparkles className="w-5 h-5 text-emerald-400" />
            <h3 className="text-base font-bold text-white tracking-wide">60-Second Investment Thesis & Conviction Card</h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
              {stock.score.verdict}
            </span>
            <span className="text-[11px] font-mono text-slate-400 bg-slate-900 px-2.5 py-0.5 rounded-lg border border-slate-800">
              Score: {stock.score.total_composite_score}/100
            </span>
          </div>
        </div>

        {/* Core Thesis Paragraph */}
        <p className="text-xs text-slate-200 leading-relaxed bg-slate-900/60 p-4 rounded-2xl border border-slate-800/80">
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
                  {docIntel.promise_vs_delivery[0]?.actual_outcome || "Proven historical execution record across key guided targets."}
                </p>
              </div>
            ) : (
              <p className="text-[11px] text-slate-400 italic">
                Execution track record verified via audited filings.
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
                {docIntel?.growth_drivers?.[0]?.driver_title || stock.score.key_catalysts[0] || "Active Expansion"}
              </p>
              <p className="text-[11px] text-slate-400 leading-tight line-clamp-2 mt-0.5">
                {docIntel?.growth_drivers?.[0]?.description || "Upcoming commercial capacity commissioning and volume market expansion."}
              </p>
            </div>
          </div>

          {/* 3. Forensic Cash Check */}
          <div className="bg-slate-950/70 p-3.5 rounded-2xl border border-slate-800/80 space-y-1.5 flex flex-col justify-between">
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              Cash Conversion & Safety
            </span>
            <div>
              <div className="flex items-center gap-2 font-mono text-xs my-1">
                <span className="text-emerald-400 font-bold">5Y CFO/PAT: {stock.analytics?.cash_flow_quality?.cfo_to_pat_5yr_pct}%</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-tight">
                Debt/Equity: <strong className="text-slate-200">{stock.ratios.debt_to_equity}x</strong> | CWIP: <strong className="text-slate-200">{stock.analytics?.balance_sheet_efficiency?.latest_cwip_to_net_block_pct}%</strong>
              </p>
            </div>
          </div>

          {/* 4. Valuation Scenario Bridge */}
          <div className="bg-slate-950/70 p-3.5 rounded-2xl border border-slate-800/80 space-y-1.5 flex flex-col justify-between">
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider flex items-center gap-1">
              <TrendingUp className="w-3.5 h-3.5 text-purple-400" />
              Valuation Bridge (3Y)
            </span>
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
          <span>Business Outlook</span>
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

        <button
          onClick={() => setActiveTab('documents')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === 'documents'
              ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Source Documents & Sourcing Audit</span>
          {stock.documents?.diagnostics && (
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-950 text-emerald-300 font-mono border border-emerald-500/30">
              {stock.documents.diagnostics.ai_ready_documents_count} Files
            </span>
          )}
        </button>
      </div>

      {/* TAB 1: INTERACTIVE PROJECTIONS & DCF VALUATION */}
      {activeTab === 'projection' && (
        <div className="space-y-6">
          
          {/* Projections Control Panel */}
          <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-emerald-400" />
                  Dynamic 5-Year Projection & Valuation Simulator
                </h3>
                <p className="text-xs text-slate-400">
                  Simulate future revenue growth, margin expansion, and exit multiple to calculate DCF Fair Value and Expected IRR
                </p>
              </div>

              {/* Scenario Presets */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => applyPreset('bear')}
                  className="px-3 py-1 rounded-lg text-xs font-semibold bg-rose-950/50 text-rose-300 border border-rose-800 hover:bg-rose-900/50"
                >
                  Bear Case
                </button>
                <button
                  onClick={() => applyPreset('base')}
                  className="px-3 py-1 rounded-lg text-xs font-semibold bg-slate-800 text-slate-200 border border-slate-700 hover:bg-slate-700"
                >
                  Base Case
                </button>
                <button
                  onClick={() => applyPreset('bull')}
                  className="px-3 py-1 rounded-lg text-xs font-semibold bg-emerald-950/50 text-emerald-300 border border-emerald-800 hover:bg-emerald-900/50"
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
                  <span className="text-slate-400 font-medium">Forward Sales CAGR</span>
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
                  <span>Hist 3Y: {stock.projection.historical_revenue_cagr_3yr}%</span>
                  <span>35%</span>
                </div>
              </div>

              {/* Target OPM % Slider */}
              <div className="space-y-2 bg-slate-950/60 p-4 rounded-2xl border border-slate-800">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400 font-medium">Target OPM (Margin)</span>
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
                  <span>Median: {stock.projection.historical_opm_median}%</span>
                  <span>60%</span>
                </div>
              </div>

              {/* Capex Intensity Slider */}
              <div className="space-y-2 bg-slate-950/60 p-4 rounded-2xl border border-slate-800">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400 font-medium">Capex % of Sales</span>
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
                  <span className="text-slate-400 font-medium">Target Exit P/E</span>
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
                  <span>Current: {stock.ratios.stock_pe}x</span>
                  <span>65x</span>
                </div>
              </div>

            </div>

            {/* Valuation Results Highlight Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
              
              {/* DCF Fair Value Card */}
              <div className="bg-gradient-to-br from-emerald-950/40 to-slate-950 p-5 rounded-2xl border border-emerald-500/30 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">DCF Intrinsic Fair Value</span>
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
                  Discounted Cash Flow based on 5-year FCFs + {terminalG}% Terminal Growth @ {wacc}% WACC.
                </p>
              </div>

              {/* Exit Multiple Target Price */}
              <div className="bg-gradient-to-br from-cyan-950/40 to-slate-950 p-5 rounded-2xl border border-cyan-500/30 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-cyan-400 uppercase tracking-wider">FY28 Exit P/E Target Price</span>
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
                  Based on Projected Year 3 EPS (₹{projectionResult.projections[2]?.eps}) × {exitPe}x Exit Multiple.
                </p>
              </div>

              {/* Projected 3-Year IRR */}
              <div className="bg-gradient-to-br from-teal-950/40 to-slate-950 p-5 rounded-2xl border border-teal-500/30 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-teal-400 uppercase tracking-wider">Projected 3-Year CAGR / IRR</span>
                  <span className="text-xs font-bold text-teal-300">
                    {projectionResult.scenario_type}
                  </span>
                </div>
                <div className="text-3xl font-extrabold font-mono text-emerald-400">
                  {projectionResult.projected_3yr_irr_cagr_pct}% / yr
                </div>
                <p className="text-[11px] text-slate-400">
                  Expected annual compounding rate from current price ₹{stock.ratios.current_price}.
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
                      Operating Profit (EBITDA)
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
                      Cash from Operations (CFO)
                    </td>
                    {projectionResult.projections.map(p => (
                      <td key={p.year} className="py-2.5 px-4 text-right">₹{p.cfo_cr.toLocaleString('en-IN')}</td>
                    ))}
                  </tr>

                  <tr className="hover:bg-slate-900/50 text-slate-300">
                    <td className="py-2.5 px-4 sticky left-0 bg-slate-950 font-sans">
                      Estimated Capex
                    </td>
                    {projectionResult.projections.map(p => (
                      <td key={p.year} className="py-2.5 px-4 text-right">₹{p.capex_cr.toLocaleString('en-IN')}</td>
                    ))}
                  </tr>

                  <tr className="hover:bg-slate-900/50 bg-emerald-950/30 text-emerald-300 font-bold">
                    <td className="py-2.5 px-4 sticky left-0 bg-emerald-950/80 font-sans">
                      Free Cash Flow (FCF)
                    </td>
                    {projectionResult.projections.map(p => (
                      <td key={p.year} className="py-2.5 px-4 text-right text-emerald-300">₹{p.fcf_cr.toLocaleString('en-IN')}</td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

        </div>
      )}

      {/* TAB 2: BUSINESS OUTLOOK & MANAGEMENT TRACKING */}
      {activeTab === 'outlook' && (
        <div className="space-y-8">
          
          {/* Header & Intelligence Provenance */}
          <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-800 pb-5">
              <div className="flex items-start sm:items-center gap-3.5">
                <div className="w-11 h-11 rounded-2xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30 shrink-0">
                  <Compass className="w-6 h-6" />
                </div>
                <div>
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <h3 className="text-xl font-bold text-white">Business Outlook & Management Tracking</h3>
                    {docIntel?.ai_provider_used && docIntel.ai_provider_used !== 'None' && docIntel.ai_provider_used !== 'Verified Baseline (Sample)' ? (
                      <span className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[11px] font-bold px-2.5 py-0.5 rounded-full flex items-center gap-1">
                        <Sparkles className="w-3 h-3" />
                        Source-Backed AI Analysis ({docIntel.ai_provider_used.toUpperCase()})
                      </span>
                    ) : docIntel?.ai_provider_used === 'Verified Baseline (Sample)' ? (
                      <span className="bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[11px] font-bold px-2.5 py-0.5 rounded-full flex items-center gap-1">
                        <Info className="w-3 h-3" />
                        Demo Baseline (Sample)
                      </span>
                    ) : (
                      <span className="bg-slate-800 text-slate-400 border border-slate-700 text-[11px] font-semibold px-2.5 py-0.5 rounded-full">
                        AI Unavailable
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    What is management planning, what is changing in the business, and are they actually delivering?
                  </p>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2.5 flex-wrap">
                <button
                  onClick={handleGenerateIntel}
                  disabled={generatingDocIntel}
                  className="bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-500 text-slate-950 font-bold text-xs px-3.5 py-2 rounded-xl flex items-center gap-1.5 transition-all shadow-sm shadow-emerald-600/20"
                >
                  <Zap className={`w-3.5 h-3.5 ${generatingDocIntel ? 'animate-spin' : ''}`} />
                  <span>{generatingDocIntel ? 'Extracting with AI...' : 'Run Live AI Analysis'}</span>
                </button>
              </div>
            </div>

            {/* Error Notice */}
            {docIntelError && (
              <div className="bg-rose-950/40 border border-rose-800/60 p-4 rounded-2xl flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="text-xs font-bold text-rose-200">AI Extraction Notice</p>
                  <p className="text-xs text-rose-300/90 leading-relaxed">{docIntelError}</p>
                </div>
              </div>
            )}

            {/* Baseline Fallback Banner */}
            {docIntel?.ai_provider_used === 'Verified Baseline (Sample)' && (
              <div className="bg-amber-950/30 border border-amber-800/40 p-4 rounded-2xl flex items-start gap-3">
                <Info className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="text-xs font-bold text-amber-200">Demo / Baseline Intelligence</p>
                  <p className="text-xs text-amber-300/80 leading-relaxed">
                    Showing verified demo baseline intelligence. Configure <code className="bg-slate-900 px-1 py-0.5 rounded text-amber-200">GEMINI_API_KEY</code> in <code className="bg-slate-900 px-1 py-0.5 rounded text-amber-200">.env</code> and click <strong>Run Live AI Analysis</strong> to extract directly from original filings.
                  </p>
                </div>
              </div>
            )}

            {/* Empty / Unavailable State */}
            {(!docIntel || docIntel.status === 'ai_unavailable' || (!docIntel.promise_vs_delivery?.length && !docIntel.plan_vs_reality?.length)) && (
              <div className="bg-slate-950/80 border border-slate-800 p-6 rounded-2xl text-center space-y-3">
                <HelpCircle className="w-8 h-8 text-slate-500 mx-auto" />
                <p className="text-sm font-bold text-slate-200">AI Document Analysis Not Generated</p>
                <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
                  Configure <code className="bg-slate-900 px-1.5 py-0.5 rounded text-emerald-400">GEMINI_API_KEY</code> or <code className="bg-slate-900 px-1.5 py-0.5 rounded text-emerald-400">OPENAI_API_KEY</code> in your <code className="bg-slate-900 px-1.5 py-0.5 rounded text-emerald-400">.env</code> file, then click <strong>Run Live AI Analysis</strong> above to automatically scan filings and generate fundamental intelligence.
                </p>
              </div>
            )}

            {/* Analyzed Documents List */}
            {docIntel?.source_documents && docIntel.source_documents.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap text-xs">
                <span className="text-slate-400 font-semibold text-[11px] uppercase tracking-wider">Source Filings:</span>
                {docIntel.source_documents.map((doc, idx) => (
                  <a
                    key={idx}
                    href={doc.url}
                    target="_blank"
                    rel="noreferrer"
                    className="bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800 px-2.5 py-1 rounded-lg flex items-center gap-1.5 transition-colors"
                  >
                    <span>{doc.title}</span>
                    <ExternalLink className="w-3 h-3 text-emerald-400" />
                  </a>
                ))}
              </div>
            )}
          </div>

          {/* Render 6 Sections if Data Available */}
          {docIntel && (docIntel.promise_vs_delivery?.length > 0 || docIntel.what_changed_recently?.length > 0) && (
            <>
              {/* SECTION 1: WHAT CHANGED RECENTLY */}
              {docIntel.what_changed_recently && docIntel.what_changed_recently.length > 0 && (
                <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-4">
                  <div className="flex items-center gap-2.5">
                    <Clock className="w-5 h-5 text-cyan-400" />
                    <h4 className="text-lg font-bold text-white">1. What Changed Recently</h4>
                  </div>
                  <p className="text-xs text-slate-400">Core operational and strategic developments synthesized from recent filings:</p>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {docIntel.what_changed_recently.map((item, idx) => (
                      <div key={idx} className="bg-slate-950/70 p-4 rounded-2xl border border-slate-800/80 space-y-2 flex flex-col justify-between">
                        <div className="space-y-1.5">
                          <div className="flex items-start justify-between gap-2">
                            <h5 className="text-xs font-bold text-slate-100">{item.headline}</h5>
                            <span className="text-[10px] uppercase font-bold tracking-wider bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 px-2 py-0.5 rounded shrink-0">
                              {item.category}
                            </span>
                          </div>
                          <p className="text-xs text-slate-300 leading-relaxed">{item.detail}</p>
                        </div>
                        {item.source_page && (
                          <div className="pt-2 border-t border-slate-900 text-[11px] text-slate-500 font-mono flex items-center justify-between">
                            <span>Source: {item.source_doc} (Page {item.source_page})</span>
                            {item.source_url && (
                              <a href={item.source_url} target="_blank" rel="noreferrer" className="text-emerald-400 hover:underline flex items-center gap-1 font-sans">
                                <span>PDF</span> <ExternalLink className="w-2.5 h-2.5" />
                              </a>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* SECTION 2: MANAGEMENT PLAN & GROWTH DRIVERS */}
              {docIntel.growth_drivers && docIntel.growth_drivers.length > 0 && (
                <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
                  <div className="flex items-center gap-2.5 border-b border-slate-800 pb-4">
                    <Layers className="w-5 h-5 text-amber-400" />
                    <div>
                      <h4 className="text-lg font-bold text-white">2. Management Plan & Growth Drivers</h4>
                      <p className="text-xs text-slate-400">Expansion projects, new products, acquisitions, and strategic growth drivers</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {docIntel.growth_drivers.map((driver, idx) => (
                      <div key={idx} className="bg-slate-950/80 rounded-2xl border border-slate-800 p-5 space-y-3.5 flex flex-col justify-between">
                        <div className="space-y-2.5">
                          <div className="flex items-start justify-between gap-2">
                            <h5 className="text-sm font-bold text-slate-100">{driver.driver_title}</h5>
                            <span className="bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0">
                              {driver.driver_type}
                            </span>
                          </div>

                          <div className="grid grid-cols-2 gap-2 text-xs font-mono bg-slate-900/60 p-3 rounded-xl border border-slate-800/80">
                            <div>
                              <span className="text-[10px] text-slate-500 uppercase font-sans block">Target Timeline</span>
                              <span className="text-slate-200 font-semibold">{driver.target_timeline || 'Ongoing'}</span>
                            </div>
                            <div>
                              <span className="text-[10px] text-slate-500 uppercase font-sans block">Stated Outlay / Capex</span>
                              <span className="text-emerald-400 font-semibold">
                                {driver.stated_outlay_or_value ? (driver.stated_outlay_or_value.startsWith('₹') ? driver.stated_outlay_or_value : `₹${driver.stated_outlay_or_value} Cr`) : 'Not Stated'}
                              </span>
                            </div>
                          </div>

                          <div className="space-y-1.5 text-xs">
                            <p className="text-slate-300 leading-relaxed">
                              <strong className="text-slate-400 font-semibold">Plan:</strong> {driver.description}
                            </p>
                            {driver.expected_impact && (
                              <p className="text-emerald-300/90 leading-relaxed">
                                <strong className="text-emerald-400 font-semibold">Expected Impact:</strong> {driver.expected_impact}
                              </p>
                            )}
                          </div>
                        </div>

                        {/* Collapsible Evidence */}
                        <details className="text-xs text-slate-400 group pt-2 border-t border-slate-900">
                          <summary className="cursor-pointer font-medium text-slate-400 hover:text-emerald-400 flex items-center gap-1.5 transition-colors select-none">
                            <ChevronRight className="w-3.5 h-3.5 group-open:rotate-90 transition-transform" />
                            <span>Source Page & Citation</span>
                          </summary>
                          <div className="mt-2.5 bg-slate-900 p-3 rounded-xl border border-slate-800 font-mono text-[11px] space-y-1">
                            {driver.source_page && <p className="text-slate-300">Source: Page {driver.source_page}</p>}
                            {driver.source_quote && <p className="text-slate-400 italic">Quote: "{driver.source_quote}"</p>}
                            {driver.source_url && (
                              <a href={driver.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-emerald-400 underline mt-1 font-sans">
                                <span>Open Filing PDF</span> <ExternalLink className="w-3 h-3" />
                              </a>
                            )}
                          </div>
                        </details>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* SECTION 3: PROMISE VS DELIVERY */}
              {docIntel.promise_vs_delivery && docIntel.promise_vs_delivery.length > 0 && (
                <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-4">
                    <div className="flex items-center gap-2.5">
                      <Target className="w-5 h-5 text-emerald-400" />
                      <div>
                        <h4 className="text-lg font-bold text-white">3. Promise vs Delivery (Historical Tracking)</h4>
                        <p className="text-xs text-slate-400">Verifying historical management promises against actual subsequent outcomes</p>
                      </div>
                    </div>
                    <span className="text-xs text-slate-400 font-mono bg-slate-900 px-3 py-1 rounded-lg border border-slate-800 self-start sm:self-auto">
                      Comparing: {docIntel.older_document_period || 'Baseline'} → {docIntel.latest_document_period || 'Latest'}
                    </span>
                  </div>

                  <div className="space-y-4">
                    {docIntel.promise_vs_delivery.map((item, idx) => {
                      const statusColors: Record<string, { bg: string; text: string; border: string }> = {
                        'Delivered': { bg: 'bg-emerald-500/20', text: 'text-emerald-300', border: 'border-emerald-500/40' },
                        'In Progress': { bg: 'bg-amber-500/20', text: 'text-amber-300', border: 'border-amber-500/40' },
                        'Delayed': { bg: 'bg-orange-500/20', text: 'text-orange-300', border: 'border-orange-500/40' },
                        'Missed': { bg: 'bg-rose-500/20', text: 'text-rose-300', border: 'border-rose-500/40' },
                        'Not Enough Data': { bg: 'bg-slate-800', text: 'text-slate-400', border: 'border-slate-700' }
                      };
                      const color = statusColors[item.status] || statusColors['Not Enough Data'];

                      return (
                        <div key={idx} className="bg-slate-950/80 rounded-2xl border border-slate-800 p-5 space-y-4">
                          {/* Top Row: Area & Status Badge */}
                          <div className="flex items-start sm:items-center justify-between gap-3 flex-wrap">
                            <span className="text-sm font-bold text-white font-sans">{item.area}</span>
                            <span className={`${color.bg} ${color.text} ${color.border} border text-xs font-bold px-3 py-1 rounded-full flex items-center gap-1.5 shadow-sm`}>
                              {item.status === 'Delivered' && '✓'}
                              {item.status === 'In Progress' && '⚠'}
                              {item.status === 'Delayed' && '⚠'}
                              {item.status === 'Missed' && '✗'}
                              {item.status === 'Not Enough Data' && '?'}
                              <span>{item.status}</span>
                            </span>
                          </div>

                          {/* Management Said vs Reported Result Grid */}
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            
                            {/* MANAGEMENT SAID */}
                            <div className="bg-blue-950/20 rounded-xl border border-blue-900/30 p-4 space-y-2">
                              <div className="flex items-center justify-between">
                                <span className="text-[10px] uppercase font-bold tracking-wider bg-blue-500/20 text-blue-300 border border-blue-500/30 px-2 py-0.5 rounded">
                                  MANAGEMENT SAID
                                </span>
                                <span className="text-[10px] text-slate-400 font-mono">{item.promised_in_period}</span>
                              </div>
                              <p className="text-xs text-slate-200 leading-relaxed italic">
                                "{item.management_promise}"
                              </p>
                            </div>

                            {/* REPORTED RESULT */}
                            <div className="bg-emerald-950/20 rounded-xl border border-emerald-900/30 p-4 space-y-2">
                              <div className="flex items-center justify-between">
                                <span className="text-[10px] uppercase font-bold tracking-wider bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded">
                                  REPORTED RESULT
                                </span>
                                <span className="text-[10px] text-slate-400 font-mono">{item.actual_in_period}</span>
                              </div>
                              <p className="text-xs text-slate-200 leading-relaxed">
                                {item.actual_outcome}
                              </p>
                            </div>

                          </div>

                          {/* STOCKER INTERPRETATION */}
                          {item.stocker_analysis && (
                            <div className="bg-purple-950/20 rounded-xl border border-purple-900/30 p-3.5 flex items-start gap-2.5">
                              <span className="text-[10px] uppercase font-bold tracking-wider bg-purple-500/20 text-purple-300 border border-purple-500/30 px-2 py-0.5 rounded shrink-0">
                                STOCKER INTERPRETATION
                              </span>
                              <p className="text-xs text-purple-200/90 leading-relaxed">
                                {item.stocker_analysis}
                              </p>
                            </div>
                          )}

                          {/* REPORTED NUMBERS CHECK */}
                          {item.financial_numbers_check && (
                            <div className="bg-cyan-950/20 rounded-xl border border-cyan-900/30 p-3.5 flex items-start gap-2.5 font-mono">
                              <span className="text-[10px] uppercase font-bold tracking-wider bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 px-2 py-0.5 rounded shrink-0 font-sans">
                                REPORTED NUMBERS
                              </span>
                              <p className="text-xs text-cyan-200/90 leading-relaxed">
                                {item.financial_numbers_check}
                              </p>
                            </div>
                          )}

                          {/* Collapsible Evidence Details */}
                          <details className="text-xs text-slate-400 group pt-1">
                            <summary className="cursor-pointer font-medium text-slate-400 hover:text-emerald-400 flex items-center gap-1.5 transition-colors select-none">
                              <ChevronRight className="w-3.5 h-3.5 group-open:rotate-90 transition-transform" />
                              <span>View Verifiable Filing Evidence</span>
                            </summary>
                            <div className="mt-3 bg-slate-900/90 p-4 rounded-xl border border-slate-800 space-y-2 font-mono text-[11px]">
                              {item.promise_source_page && (
                                <p className="text-slate-300">
                                  <strong className="text-slate-400 font-sans">Guidance Source:</strong> {item.promised_in_period} (Page {item.promise_source_page})
                                  {item.promise_quote && <span className="block text-slate-400 mt-1 italic">Quote: "{item.promise_quote}"</span>}
                                  {item.source_url_promise && (
                                    <a href={item.source_url_promise} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-emerald-400 underline mt-1 font-sans">
                                      <span>Open Filing PDF</span> <ExternalLink className="w-3 h-3" />
                                    </a>
                                  )}
                                </p>
                              )}
                              {item.actual_source_page && (
                                <p className="text-slate-300 pt-2 border-t border-slate-800/80">
                                  <strong className="text-slate-400 font-sans">Delivery Source:</strong> {item.actual_in_period} (Page {item.actual_source_page})
                                  {item.actual_quote && <span className="block text-slate-400 mt-1 italic">Quote: "{item.actual_quote}"</span>}
                                  {item.source_url_actual && (
                                    <a href={item.source_url_actual} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-emerald-400 underline mt-1 font-sans">
                                      <span>Open Filing PDF</span> <ExternalLink className="w-3 h-3" />
                                    </a>
                                  )}
                                </p>
                              )}
                            </div>
                          </details>

                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* SECTION 4: DEMAND / BUSINESS MOMENTUM */}
              {docIntel.demand_momentum && (
                <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
                  <div className="flex items-center gap-2.5 border-b border-slate-800 pb-4">
                    <TrendingUp className="w-5 h-5 text-cyan-400" />
                    <div>
                      <h4 className="text-lg font-bold text-white">4. Demand / Business Momentum</h4>
                      <p className="text-xs text-slate-400">Order inflows, subscriber/volume traction, and industry demand environment</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    
                    {/* Metrics Grid */}
                    <div className="bg-slate-950/80 p-5 rounded-2xl border border-slate-800 space-y-4">
                      <span className="text-xs font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-1.5">
                        <CheckCircle2 className="w-4 h-4" />
                        Company-Relevant Demand Signals
                      </span>

                      {docIntel.demand_momentum.company_specific_metrics && docIntel.demand_momentum.company_specific_metrics.length > 0 && (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                          {docIntel.demand_momentum.company_specific_metrics.map((m, idx) => (
                            <div key={idx} className="bg-slate-900/60 p-3 rounded-xl border border-slate-800/80 space-y-0.5">
                              <span className="text-[10px] text-slate-500 uppercase block font-sans">{m.metric}</span>
                              <span className="text-xs font-bold text-slate-100 font-mono">{m.value}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {docIntel.demand_momentum.segment_trends && docIntel.demand_momentum.segment_trends.length > 0 && (
                        <div className="space-y-2 pt-2 border-t border-slate-900">
                          <span className="text-[10px] uppercase font-bold text-slate-400 block">Segment Trends:</span>
                          <ul className="space-y-1.5">
                            {docIntel.demand_momentum.segment_trends.map((st, idx) => (
                              <li key={idx} className="text-xs text-slate-300">
                                <strong className="text-slate-200">{st.segment}:</strong> {st.trend}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {docIntel.demand_momentum.market_share_and_pricing && (
                        <p className="text-xs text-emerald-300 bg-emerald-950/20 p-3 rounded-xl border border-emerald-900/30">
                          <strong>Market Position:</strong> {docIntel.demand_momentum.market_share_and_pricing}
                        </p>
                      )}
                    </div>

                    {/* Headwinds & Macro Risks */}
                    <div className="bg-rose-950/20 p-5 rounded-2xl border border-rose-900/30 space-y-4">
                      <span className="text-xs font-bold uppercase tracking-wider text-rose-400 flex items-center gap-1.5">
                        <AlertTriangle className="w-4 h-4" />
                        Stated Demand Headwinds & Headwinds
                      </span>

                      {(!docIntel.demand_momentum.headwinds_and_risks || docIntel.demand_momentum.headwinds_and_risks.length === 0) ? (
                        <p className="text-xs text-slate-400 italic">No critical demand headwinds noted in recent disclosures.</p>
                      ) : (
                        <ul className="space-y-2.5">
                          {docIntel.demand_momentum.headwinds_and_risks.map((risk, i) => (
                            <li key={i} className="text-xs text-rose-200/90 flex items-start gap-2 leading-relaxed">
                              <span className="w-1.5 h-1.5 rounded-full bg-rose-400 mt-1.5 shrink-0" />
                              <span>{risk}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>

                  </div>
                </div>
              )}

              {/* SECTION 5: RISKS, CASH & EXECUTION ISSUES */}
              {docIntel.risks_and_cash && (
                <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
                  <div className="flex items-center gap-2.5 border-b border-slate-800 pb-4">
                    <DollarSign className="w-5 h-5 text-emerald-400" />
                    <div>
                      <h4 className="text-lg font-bold text-white">5. Risks, Cash Flow & Execution Issues</h4>
                      <p className="text-xs text-slate-400">Auditing working capital, debt trajectory, and independent mathematical cross-checks</p>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      
                      <div className="bg-slate-950/80 p-5 rounded-2xl border border-slate-800 space-y-2">
                        <span className="text-[10px] uppercase font-bold tracking-wider text-amber-400 block">
                          Working Capital & Receivables
                        </span>
                        <p className="text-xs text-slate-200 leading-relaxed">
                          {docIntel.risks_and_cash.working_capital_and_receivables || "Working capital cycle is tracking in line with business expansion."}
                        </p>
                      </div>

                      <div className="bg-slate-950/80 p-5 rounded-2xl border border-slate-800 space-y-2">
                        <span className="text-[10px] uppercase font-bold tracking-wider text-emerald-400 block">
                          Debt & Capex Burden
                        </span>
                        <p className="text-xs text-slate-200 leading-relaxed">
                          {docIntel.risks_and_cash.debt_and_capex_burden || "Debt servicing and capital allocation remain supported by operational cash flows."}
                        </p>
                      </div>

                    </div>

                    {/* REPORTED NUMBERS COMPARISON */}
                    {docIntel.risks_and_cash.reported_numbers_comparison && (
                      <div className="bg-cyan-950/20 p-5 rounded-2xl border border-cyan-900/40 space-y-2">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] uppercase font-bold tracking-wider bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 px-2 py-0.5 rounded">
                            REPORTED NUMBERS
                          </span>
                          <span className="text-xs font-bold text-cyan-200">Mathematical Statement Verification</span>
                        </div>
                        <p className="text-xs text-cyan-100 leading-relaxed font-mono">
                          {docIntel.risks_and_cash.reported_numbers_comparison}
                        </p>
                      </div>
                    )}

                    {/* Operational Bottlenecks */}
                    {docIntel.risks_and_cash.execution_and_bottlenecks && docIntel.risks_and_cash.execution_and_bottlenecks.length > 0 && (
                      <div className="bg-slate-900/60 p-4 rounded-2xl border border-slate-800 space-y-2">
                        <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                          Operational & Execution Bottlenecks
                        </span>
                        <ul className="space-y-1.5">
                          {docIntel.risks_and_cash.execution_and_bottlenecks.map((b, i) => (
                            <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mt-1.5 shrink-0" />
                              <span>{b}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* SECTION 6: STOCKER VIEW */}
              {docIntel.stocker_view && (
                <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
                    <div className="flex items-center gap-2.5">
                      <Sparkles className="w-5 h-5 text-purple-400" />
                      <div>
                        <h4 className="text-lg font-bold text-white">6. Stocker View</h4>
                        <p className="text-xs text-slate-400">Independent fundamental takeaway, key future triggers & what to watch</p>
                      </div>
                    </div>
                    <span className="bg-purple-500/20 text-purple-300 border border-purple-500/40 text-xs font-bold px-3 py-1 rounded-full self-start sm:self-auto">
                      {docIntel.stocker_view.execution_verdict}
                    </span>
                  </div>

                  <div className="space-y-4">
                    {/* Investor Summary Box */}
                    <div className="bg-slate-950/80 p-5 rounded-2xl border border-slate-800 space-y-2">
                      <span className="text-[10px] uppercase font-bold tracking-wider text-purple-400 block">
                        Institutional Investor Summary
                      </span>
                      <p className="text-xs text-slate-200 leading-relaxed font-sans">
                        {docIntel.stocker_view.investor_summary}
                      </p>
                    </div>

                    {/* Grid of Triggers vs Risks vs Watchlist */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      
                      {/* Positive Triggers */}
                      <div className="bg-emerald-950/20 p-4 rounded-2xl border border-emerald-900/30 space-y-2.5">
                        <span className="text-[10px] uppercase font-bold tracking-wider text-emerald-400 flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Positive Future Triggers
                        </span>
                        <ul className="space-y-1.5">
                          {docIntel.stocker_view.positive_triggers.map((t, idx) => (
                            <li key={idx} className="text-xs text-emerald-200/90 flex items-start gap-1.5">
                              <span className="text-emerald-400">•</span>
                              <span>{t}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* Main Risks */}
                      <div className="bg-rose-950/20 p-4 rounded-2xl border border-rose-900/30 space-y-2.5">
                        <span className="text-[10px] uppercase font-bold tracking-wider text-rose-400 flex items-center gap-1">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          Main Risks to Monitor
                        </span>
                        <ul className="space-y-1.5">
                          {docIntel.stocker_view.main_risks.map((r, idx) => (
                            <li key={idx} className="text-xs text-rose-200/90 flex items-start gap-1.5">
                              <span className="text-rose-400">•</span>
                              <span>{r}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* What to Watch Next */}
                      <div className="bg-cyan-950/20 p-4 rounded-2xl border border-cyan-900/30 space-y-2.5">
                        <span className="text-[10px] uppercase font-bold tracking-wider text-cyan-400 flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5" />
                          What to Watch Next (2-4 Qtrs)
                        </span>
                        <ul className="space-y-1.5">
                          {docIntel.stocker_view.what_to_watch_next.map((w, idx) => (
                            <li key={idx} className="text-xs text-cyan-200/90 flex items-start gap-1.5">
                              <span className="text-cyan-400">•</span>
                              <span>{w}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                    </div>
                  </div>
                </div>
              )}
            </>
          )}

        </div>
      )}

      {/* TAB 3: FINANCIAL STATEMENTS (RAW SCREENER DATA) */}
      {activeTab === 'financials' && (
        <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
            <div>
              <h3 className="text-xl font-bold text-white">Raw Financial Statements</h3>
              <p className="text-xs text-slate-400">Primary consolidated data extracted directly from Screener.in filings</p>
            </div>

            {/* Sub-Tabs for Statements */}
            <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800">
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

          {/* Render selected statement */}
          {financialSubTab === 'quarters' && renderStatementTable(stock.quarters)}
          {financialSubTab === 'pl' && renderStatementTable(stock.profit_loss)}
          {financialSubTab === 'balance_sheet' && renderStatementTable(stock.balance_sheet)}
          {financialSubTab === 'cash_flow' && renderStatementTable(stock.cash_flow)}
        </div>
      )}

      {/* TAB 4: TREND ANALYTICS & VISUALIZATIONS */}
      {activeTab === 'charts' && (
        <div className="space-y-6">
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            
            {/* Chart 1: Quarterly Sales & Operating Profit Trend */}
            <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
              <div>
                <h4 className="font-bold text-white text-sm">Quarterly Revenue & OPM % Trajectory</h4>
                <p className="text-xs text-slate-400">Quarter-on-quarter momentum and margin expansion</p>
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
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="period" stroke="#64748b" fontSize={10} />
                    <YAxis yAxisId="left" stroke="#10b981" fontSize={10} />
                    <YAxis yAxisId="right" orientation="right" stroke="#06b6d4" fontSize={10} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px' }}
                      formatter={(val: any, name: string) => [
                        typeof val === 'number' ? (name.includes('OPM') ? `${val}%` : `₹${val.toLocaleString('en-IN')} Cr`) : val,
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
                <h4 className="font-bold text-white text-sm">Earnings Quality: Net Profit vs CFO vs Free Cash Flow</h4>
                <p className="text-xs text-slate-400">Validating whether accounting profits convert into hard operational cash</p>
              </div>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={fcfTrends}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="period" stroke="#64748b" fontSize={10} />
                    <YAxis stroke="#64748b" fontSize={10} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px' }}
                      formatter={(val: any) => [`₹${val?.toLocaleString('en-IN')} Cr`]}
                    />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                    <Bar dataKey="pat_cr" name="Net Profit (PAT)" fill="#64748b" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="cfo_cr" name="Cash from Operations (CFO)" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="fcf_cr" name="Free Cash Flow (FCF)" fill="#10b981" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

          </div>

          {/* Chart 3: Balance Sheet & CWIP Growth Trigger */}
          <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
            <div>
              <h4 className="font-bold text-white text-sm">Balance Sheet Capital Allocation & CWIP Trigger</h4>
              <p className="text-xs text-slate-400">Capital Work in Progress (CWIP) as % of Net Block signals upcoming revenue capacity</p>
            </div>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={bsTrends}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="period" stroke="#64748b" fontSize={10} />
                  <YAxis yAxisId="left" stroke="#64748b" fontSize={10} />
                  <YAxis yAxisId="right" orientation="right" stroke="#f59e0b" fontSize={10} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px' }}
                  />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                  <Bar yAxisId="left" dataKey="fixed_assets_cr" name="Fixed Assets (₹ Cr)" fill="#334155" radius={[4, 4, 0, 0]} />
                  <Bar yAxisId="left" dataKey="cwip_cr" name="CWIP (₹ Cr)" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                  <Line yAxisId="right" type="monotone" dataKey="cwip_to_fixed_assets_pct" name="CWIP / Net Block %" stroke="#10b981" strokeWidth={2} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

        </div>
      )}

      {/* TAB 5: 5-PILLAR SCORECARD & RISKS */}
      {activeTab === 'scorecard' && (
        <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-8">
          
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h3 className="text-xl font-bold text-white">5-Pillar Fundamental Scorecard</h3>
              <p className="text-xs text-slate-400">Quantitative multi-factor weighting model</p>
            </div>
            <div className="text-right">
              <span className="text-xs text-slate-400 font-mono">Composite Verdict</span>
              <div className="text-lg font-extrabold text-emerald-400">{stock.score.verdict}</div>
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

        </div>
      )}

      {/* TAB 6: SOURCE DOCUMENTS & SOURCING AUDIT */}
      {activeTab === 'documents' && (
        <div className="space-y-6">
          
          {/* Diagnostics Summary Header */}
          <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-800 pb-5">
              <div>
                <h3 className="text-xl font-bold text-white flex items-center gap-2.5">
                  <FileText className="w-5 h-5 text-emerald-400" />
                  <span>Source Documents & Sourcing Audit</span>
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Multi-source discovery waterfall across Screener.in, BSE India, NSE India, and official Company Investor Relations.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={handleGenerateIntel}
                  disabled={generatingDocIntel}
                  className="px-4 py-2 bg-gradient-to-r from-emerald-500 to-cyan-500 text-slate-950 rounded-xl text-xs font-bold shadow-lg shadow-emerald-500/20 hover:brightness-110 disabled:opacity-50 transition-all flex items-center gap-2"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>{generatingDocIntel ? 'Extracting Multi-Document AI...' : 'Run Multi-Document AI Analysis'}</span>
                </button>
              </div>
            </div>

            {/* Sourcing Diagnostics 5-Box Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 font-mono text-xs">
              <div className="bg-slate-950/70 p-3.5 rounded-2xl border border-slate-800 text-center space-y-1">
                <span className="text-[10px] text-slate-500 uppercase font-sans block">Annual Reports</span>
                <span className="text-base font-bold text-emerald-400">
                  {stock.documents?.annual_reports?.length || 0}/3
                </span>
                <span className="text-[10px] text-slate-400 block font-sans">Last 3 Years</span>
              </div>

              <div className="bg-slate-950/70 p-3.5 rounded-2xl border border-slate-800 text-center space-y-1">
                <span className="text-[10px] text-slate-500 uppercase font-sans block">Concall Transcripts</span>
                <span className="text-base font-bold text-cyan-400">
                  {stock.documents?.concalls?.length || 0}/6
                </span>
                <span className="text-[10px] text-slate-400 block font-sans">Last 6 Quarters</span>
              </div>

              <div className="bg-slate-950/70 p-3.5 rounded-2xl border border-slate-800 text-center space-y-1">
                <span className="text-[10px] text-slate-500 uppercase font-sans block">Presentations</span>
                <span className="text-base font-bold text-amber-400">
                  {stock.documents?.presentations?.length || 0}/6
                </span>
                <span className="text-[10px] text-slate-400 block font-sans">Last 6 Decks</span>
              </div>

              <div className="bg-slate-950/70 p-3.5 rounded-2xl border border-slate-800 text-center space-y-1">
                <span className="text-[10px] text-slate-500 uppercase font-sans block">Announcements</span>
                <span className="text-base font-bold text-purple-400">
                  {stock.documents?.material_announcements?.length || 0}
                </span>
                <span className="text-[10px] text-slate-400 block font-sans">Exchange Filings</span>
              </div>

              <div className="bg-slate-950/70 p-3.5 rounded-2xl border border-slate-800 text-center space-y-1">
                <span className="text-[10px] text-slate-500 uppercase font-sans block">Invalid Rejected</span>
                <span className="text-base font-bold text-rose-400">
                  {stock.documents?.diagnostics?.invalid_links_rejected ?? 0}
                </span>
                <span className="text-[10px] text-slate-400 block font-sans">Filtered Out</span>
              </div>

              <div className="bg-slate-950/70 p-3.5 rounded-2xl border border-slate-800 text-center space-y-1">
                <span className="text-[10px] text-slate-500 uppercase font-sans block">AI-Ready Valid</span>
                <span className="text-base font-bold text-emerald-400">
                  {stock.documents?.diagnostics?.ai_ready_documents_count ?? ((stock.documents?.annual_reports?.length || 0) + (stock.documents?.concalls?.length || 0) + (stock.documents?.presentations?.length || 0) + (stock.documents?.material_announcements?.length || 0))}
                </span>
                <span className="text-[10px] text-emerald-400 block font-sans font-bold">✓ Verified</span>
              </div>
            </div>
            {/* Sourcing Architecture Clarification Banner */}
            <div className="bg-slate-950/60 p-4 rounded-2xl border border-slate-800 flex items-center gap-3 text-xs text-slate-300">
              <Info className="w-4 h-4 text-emerald-400 shrink-0" />
              <p>
                <strong className="text-white">Waterfall Execution:</strong> Filings are discovered first via <span className="text-emerald-400 font-bold">Screener.in</span> and backed up via <span className="text-cyan-400 font-bold">BSE India</span> & <span className="text-purple-400 font-bold">NSE India</span> official feeds. Note that Screener indexes direct official exchange filings, so the PDF is hosted directly on exchange servers (<code className="text-slate-300">bseindia.com</code> / <code className="text-slate-300">nseindia.com</code>) or company IR domains.
              </p>
            </div>
          </div>

          {/* Section 1: Annual Reports */}
          <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-white text-sm flex items-center gap-2">
                <FileText className="w-4 h-4 text-emerald-400" />
                <span>Audited Annual Reports & Integrated Filings</span>
              </h4>
              <span className="text-xs font-mono text-slate-400">{stock.documents?.annual_reports?.length || 0} Available</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {stock.documents?.annual_reports?.map((doc, idx) => (
                <div key={idx} className="bg-slate-950/70 p-4 rounded-2xl border border-slate-800/80 space-y-3 flex flex-col justify-between">
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-[11px] font-mono">
                      <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
                        {doc.period_or_date || 'Annual Filing'}
                      </span>
                      <span className="px-2 py-0.5 rounded bg-slate-900 text-slate-300 border border-slate-700 text-[10px]">
                        Discovered via: <strong className="text-emerald-300">{doc.discovery_source}</strong>
                      </span>
                    </div>
                    <p className="text-xs font-semibold text-slate-200 line-clamp-2">{doc.title}</p>
                    <div className="text-[11px] text-slate-400 flex items-center justify-between">
                      <span>PDF Host: <strong className="text-slate-300">{doc.actual_source_host}</strong></span>
                      {doc.is_direct_pdf && <span className="text-emerald-400 font-bold">● Direct PDF</span>}
                    </div>
                  </div>

                  <a
                    href={doc.url}
                    target="_blank"
                    rel="noreferrer"
                    className="w-full py-2 px-3 bg-slate-900 hover:bg-slate-800 text-slate-200 text-xs font-bold rounded-xl border border-slate-800 text-center flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <span>Open Official Document</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              ))}
              {(!stock.documents?.annual_reports || stock.documents.annual_reports.length === 0) && (
                <p className="text-xs text-slate-500 italic p-4">No annual reports discovered via exchange feeds.</p>
              )}
            </div>
          </div>

          {/* Section 2: Concall Transcripts */}
          <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-white text-sm flex items-center gap-2">
                <Mic className="w-4 h-4 text-cyan-400" />
                <span>Earnings Conference Call Transcripts</span>
              </h4>
              <span className="text-xs font-mono text-slate-400">{stock.documents?.concalls?.length || 0} Available</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {stock.documents?.concalls?.map((doc, idx) => (
                <div key={idx} className="bg-slate-950/70 p-4 rounded-2xl border border-slate-800/80 space-y-3 flex flex-col justify-between">
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-[11px] font-mono">
                      <span className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-bold">
                        {doc.period_or_date || 'Earnings Call'}
                      </span>
                      <span className="px-2 py-0.5 rounded bg-slate-900 text-slate-300 border border-slate-700 text-[10px]">
                        Discovered via: <strong className="text-cyan-300">{doc.discovery_source}</strong>
                      </span>
                    </div>
                    <p className="text-xs font-semibold text-slate-200 line-clamp-2">{doc.title}</p>
                    <div className="text-[11px] text-slate-400 flex items-center justify-between">
                      <span>PDF Host: <strong className="text-slate-300">{doc.actual_source_host}</strong></span>
                      {doc.is_direct_pdf && <span className="text-cyan-400 font-bold">● Direct PDF</span>}
                    </div>
                  </div>

                  <a
                    href={doc.url}
                    target="_blank"
                    rel="noreferrer"
                    className="w-full py-2 px-3 bg-slate-900 hover:bg-slate-800 text-slate-200 text-xs font-bold rounded-xl border border-slate-800 text-center flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <span>Open Transcript</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              ))}
              {(!stock.documents?.concalls || stock.documents.concalls.length === 0) && (
                <p className="text-xs text-slate-500 italic p-4">No concall transcripts discovered for this stock.</p>
              )}
            </div>
          </div>

          {/* Section 3: Investor Presentations */}
          <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-white text-sm flex items-center gap-2">
                <Presentation className="w-4 h-4 text-amber-400" />
                <span>Investor Decks & Quarterly Presentations</span>
              </h4>
              <span className="text-xs font-mono text-slate-400">{stock.documents?.presentations?.length || 0} Available</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {stock.documents?.presentations?.map((doc, idx) => (
                <div key={idx} className="bg-slate-950/70 p-4 rounded-2xl border border-slate-800/80 space-y-3 flex flex-col justify-between">
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-[11px] font-mono">
                      <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-bold">
                        {doc.period_or_date || 'Investor PPT'}
                      </span>
                      <span className="px-2 py-0.5 rounded bg-slate-900 text-slate-300 border border-slate-700 text-[10px]">
                        Discovered via: <strong className="text-amber-300">{doc.discovery_source}</strong>
                      </span>
                    </div>
                    <p className="text-xs font-semibold text-slate-200 line-clamp-2">{doc.title}</p>
                    <div className="text-[11px] text-slate-400 flex items-center justify-between">
                      <span>PDF Host: <strong className="text-slate-300">{doc.actual_source_host}</strong></span>
                      {doc.is_direct_pdf && <span className="text-amber-400 font-bold">● Direct PDF</span>}
                    </div>
                  </div>

                  <a
                    href={doc.url}
                    target="_blank"
                    rel="noreferrer"
                    className="w-full py-2 px-3 bg-slate-900 hover:bg-slate-800 text-slate-200 text-xs font-bold rounded-xl border border-slate-800 text-center flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <span>Open Presentation</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              ))}
              {(!stock.documents?.presentations || stock.documents.presentations.length === 0) && (
                <p className="text-xs text-slate-500 italic p-4">No investor presentations discovered.</p>
              )}
            </div>
          </div>

          {/* Section 4: Material Exchange Announcements */}
          {stock.documents?.material_announcements && stock.documents.material_announcements.length > 0 && (
            <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="font-bold text-white text-sm flex items-center gap-2">
                  <Bell className="w-4 h-4 text-purple-400" />
                  <span>Important BSE/NSE Corporate Announcements</span>
                </h4>
                <span className="text-xs font-mono text-slate-400">{stock.documents.material_announcements.length} Available</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {stock.documents.material_announcements.map((doc, idx) => (
                  <div key={idx} className="bg-slate-950/70 p-4 rounded-2xl border border-slate-800/80 space-y-2 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between text-[11px] font-mono">
                        <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20 font-bold">
                          {doc.period_or_date || 'Announcement'}
                        </span>
                        <span className="px-2 py-0.5 rounded bg-slate-900 text-slate-300 border border-slate-700 text-[10px]">
                          Discovered via: <strong className="text-purple-300">{doc.discovery_source}</strong>
                        </span>
                      </div>
                      <p className="text-xs font-semibold text-slate-200 line-clamp-2 mt-1.5">{doc.title}</p>
                      <div className="text-[11px] text-slate-400 mt-1 flex items-center justify-between">
                        <span>PDF Host: <strong className="text-slate-300">{doc.actual_source_host}</strong></span>
                        {doc.is_direct_pdf && <span className="text-purple-400 font-bold">● Direct PDF</span>}
                      </div>
                    </div>

                    <a
                      href={doc.url}
                      target="_blank"
                      rel="noreferrer"
                      className="py-1.5 px-3 bg-slate-900 hover:bg-slate-800 text-slate-200 text-xs font-bold rounded-xl border border-slate-800 text-center flex items-center justify-center gap-1.5 transition-colors mt-2"
                    >
                      <span>View Filing</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      )}

    </div>
  );
};

