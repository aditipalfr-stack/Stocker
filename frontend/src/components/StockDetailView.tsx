import React, { useState, useEffect } from 'react';
import { 
  StockDetail, ProjectionAssumption, ProjectionResult, 
  FinancialStatement 
} from '../types';
import { projectStock } from '../api';
import { 
  TrendingUp, BarChart3, Sliders, FileText, ShieldAlert, 
  ExternalLink, ArrowUpRight, ArrowDownRight, RefreshCw, 
  CheckCircle2, AlertTriangle, Sparkles, Building, Layers, 
  DollarSign, Activity, FileSpreadsheet, ChevronRight, HelpCircle
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
  const [activeTab, setActiveTab] = useState<'financials' | 'charts' | 'projection' | 'concall' | 'scorecard'>('projection');
  const [financialSubTab, setFinancialSubTab] = useState<'quarters' | 'pl' | 'balance_sheet' | 'cash_flow'>('quarters');
  
  // Projection Simulator State
  const [growthRate, setGrowthRate] = useState<number>(stock.projection.assumptions.revenue_growth_rate_pct);
  const [opmRate, setOpmRate] = useState<number>(stock.projection.assumptions.target_opm_pct);
  const [capexRate, setCapexRate] = useState<number>(stock.projection.assumptions.capex_pct_of_sales);
  const [exitPe, setExitPe] = useState<number>(stock.projection.assumptions.target_exit_pe);
  const [wacc, setWacc] = useState<number>(stock.projection.assumptions.discount_rate_wacc_pct);
  const [terminalG, setTerminalG] = useState<number>(stock.projection.assumptions.terminal_growth_rate_pct);
  
  const [projectionResult, setProjectionResult] = useState<ProjectionResult>(stock.projection);
  const [isProjecting, setIsProjecting] = useState<boolean>(false);

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
          onClick={() => setActiveTab('concall')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 whitespace-nowrap ${
            activeTab === 'concall'
              ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Concall & Annual Report AI Insights</span>
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

      {/* TAB 2: CONCALL & ANNUAL REPORT AI QUALITATIVE INTELLIGENCE */}
      {activeTab === 'concall' && (
        <div className="space-y-6">
          
          {/* Concall Analysis Section */}
          <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white">Concall Transcript & Earnings Analysis</h3>
                  <p className="text-xs text-slate-400">
                    Extracted from latest corporate concall transcript & investor presentations
                  </p>
                </div>
              </div>

              {stock.documents?.concalls?.[0]?.url && (
                <a
                  href={stock.documents.concalls[0].url}
                  target="_blank"
                  rel="noreferrer"
                  className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-3 py-1.5 rounded-xl flex items-center gap-1.5 transition-colors shadow-sm"
                >
                  <span>Open Transcript PDF</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>

            {stock.concall_insights.map((concall, idx) => (
              <div key={idx} className="space-y-6">
                
                {/* CFO vs Free Cash Flow Deep-Dive */}
                <div className="bg-slate-950/70 p-5 rounded-2xl border border-slate-800 space-y-3">
                  <div className="flex items-center gap-2 text-emerald-400 text-xs font-bold uppercase tracking-wider">
                    <DollarSign className="w-4 h-4" />
                    <span>Cash Flow from Operations (CFO) & Free Cash Flow (FCF) Performance</span>
                  </div>
                  <p className="text-sm text-slate-200 leading-relaxed font-sans">
                    {concall.cfo_and_fcf_analysis}
                  </p>
                </div>

                {/* Grid of Demand Drivers vs Supply / Capex */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  
                  {/* Demand Drivers */}
                  <div className="bg-slate-900/60 p-5 rounded-2xl border border-slate-800 space-y-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-1.5">
                      <TrendingUp className="w-4 h-4" />
                      Demand Drivers & Market Share
                    </span>
                    <ul className="space-y-2.5">
                      {concall.demand_drivers.map((d, i) => (
                        <li key={i} className="text-xs text-slate-300 flex items-start gap-2 leading-relaxed">
                          <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                          <span>{d}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Supply & Capex */}
                  <div className="bg-slate-900/60 p-5 rounded-2xl border border-slate-800 space-y-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
                      <Layers className="w-4 h-4" />
                      Supply Dynamics, CWIP & Capex
                    </span>
                    <ul className="space-y-2.5">
                      {concall.supply_and_capex.map((s, i) => (
                        <li key={i} className="text-xs text-slate-300 flex items-start gap-2 leading-relaxed">
                          <ChevronRight className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                          <span>{s}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                </div>

                {/* Management Guidance Banner */}
                <div className="bg-gradient-to-r from-slate-900 to-emerald-950/30 p-5 rounded-2xl border border-emerald-500/20 space-y-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4" />
                    Management Forward Guidance & Outlook
                  </span>
                  <p className="text-xs md:text-sm text-slate-200 leading-relaxed italic">
                    "{concall.management_guidance}"
                  </p>
                </div>

                {/* Risks & Headwinds */}
                <div className="bg-rose-950/20 p-5 rounded-2xl border border-rose-900/30 space-y-3">
                  <span className="text-xs font-bold uppercase tracking-wider text-rose-400 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4" />
                    Key Business Risks & Headwinds Discussed
                  </span>
                  <ul className="space-y-2">
                    {concall.risks_and_headwinds.map((r, i) => (
                      <li key={i} className="text-xs text-rose-200/90 flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-rose-400 mt-1.5 shrink-0" />
                        <span>{r}</span>
                      </li>
                    ))}
                  </ul>
                </div>

              </div>
            ))}
          </div>

          {/* Annual Report & Forensic Checklist */}
          {stock.annual_report_insights.map((ar, idx) => (
            <div key={idx} className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
              <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                <div>
                  <h3 className="text-lg font-bold text-white">Annual Report Forensic & Governance Checklist ({ar.year})</h3>
                  <p className="text-xs text-slate-400">Auditor opinions, promoter pledging, and strategic priorities</p>
                </div>
              </div>

              {/* Forensic Metric Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 font-mono text-xs">
                {Object.entries(ar.forensic_checklist).map(([key, val]) => (
                  <div key={key} className="bg-slate-950/70 p-4 rounded-xl border border-slate-800 space-y-1">
                    <span className="text-[10px] text-slate-500 uppercase font-sans block">
                      {key.replace(/_/g, ' ')}
                    </span>
                    <span className="text-xs font-bold text-emerald-400">{val}</span>
                  </div>
                ))}
              </div>

              <div className="bg-slate-900/60 p-5 rounded-2xl border border-slate-800 space-y-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Long-Term Strategic Priorities
                </span>
                <ul className="space-y-1.5">
                  {ar.strategic_priorities.map((p, i) => (
                    <li key={i} className="text-xs text-slate-300 flex items-center gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                      <span>{p}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ))}

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

    </div>
  );
};

