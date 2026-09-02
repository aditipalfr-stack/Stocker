import React from 'react';
import { ComparisonItem } from '../types';
import { ShieldCheck, ArrowLeft, X } from 'lucide-react';
import { 
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, 
  Tooltip, Legend, CartesianGrid 
} from 'recharts';
import { ConceptHelp } from './ui/ConceptHelp';
import { DataOriginBadge } from './ui/DataOriginBadge';
import { ComparisonHighlight } from './ui/ComparisonHighlight';
import { getComparisonStanding } from '../utils/financialMetrics';
import type { ComparisonMetricKey } from '../utils/financialMetrics';

interface StockComparisonProps {
  comparisonData: ComparisonItem[];
  onRemoveSymbol: (symbol: string) => void;
  onSelectStock: (symbol: string) => void;
  onBack: () => void;
  availableSymbols: string[];
  onAddSymbol: (symbol: string) => void;
}

const isFiniteNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const formatRupees = (value: number | null | undefined) => isFiniteNumber(value) ? `₹${value.toLocaleString('en-IN')}` : '—';
const formatCrores = (value: number | null | undefined) => isFiniteNumber(value) ? `₹${value.toLocaleString('en-IN')}` : '—';
const formatPercent = (value: number | null | undefined) => isFiniteNumber(value) ? `${value}%` : '—';
const formatMultiple = (value: number | null | undefined) => isFiniteNumber(value) ? `${value}x` : '—';

export const StockComparison: React.FC<StockComparisonProps> = ({
  comparisonData,
  onRemoveSymbol,
  onSelectStock,
  onBack,
  availableSymbols,
  onAddSymbol
}) => {
  if (comparisonData.length === 0) {
    return (
      <div className="glass-panel rounded-3xl p-12 text-center space-y-4 border border-slate-800">
        <ShieldCheck className="w-12 h-12 text-slate-600 mx-auto" />
        <h3 className="text-xl font-bold text-white">No Stocks Selected for Comparison</h3>
        <p className="text-xs text-slate-400 max-w-md mx-auto">
          Please select at least 2 stocks from the universe leaderboard to compare their fundamental financials, cash conversion, and projected returns side-by-side.
        </p>
        <button
          onClick={onBack}
          className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold px-4 py-2 rounded-xl text-xs transition-colors"
        >
          Return to Leaderboard
        </button>
      </div>
    );
  }

  // Format chart data
  const scoreChartData = comparisonData.map(item => ({
    symbol: item.symbol,
    Growth: item.score_breakdown.growth,
    'Cash Quality': item.score_breakdown.cash_quality,
    Efficiency: item.score_breakdown.efficiency,
    Safety: item.score_breakdown.safety,
    Valuation: item.score_breakdown.valuation,
    Composite: item.composite_score
  }));
  const comparisonValues: Record<ComparisonMetricKey, Array<number | null | undefined>> = {
    composite_score: comparisonData.map(item => item.composite_score),
    roce_pct: comparisonData.map(item => item.roce_pct),
    fcf_yield_pct: comparisonData.map(item => item.fcf_yield_pct),
    debt_to_equity: comparisonData.map(item => item.debt_to_equity)
  };

  const directionalValue = (metric: ComparisonMetricKey, value: number | null | undefined, formatted: React.ReactNode) => (
    <ComparisonHighlight standing={getComparisonStanding(metric, value, comparisonValues[metric])}>
      {formatted}
    </ComparisonHighlight>
  );

  return (
    <div className="space-y-6 pb-12">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <button
            onClick={onBack}
            className="text-xs font-bold text-slate-400 hover:text-emerald-400 flex items-center gap-1.5 transition-colors mb-2"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Leaderboard</span>
          </button>
          <h2 className="text-2xl font-extrabold text-white tracking-tight">
            Side-by-Side Fundamental Comparison Arena
          </h2>
          <p className="text-xs text-slate-400">
            Compare key fundamental metrics, return ratios, cash conversion, and projected 3-year IRRs
          </p>
        </div>

        {/* Add more tickers dropdown */}
        <div className="flex items-center gap-2">
          <select
            onChange={(e) => {
              if (e.target.value) {
                onAddSymbol(e.target.value);
                e.target.value = '';
              }
            }}
            defaultValue=""
            className="bg-slate-900 border border-slate-700 text-xs text-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="" disabled>+ Add Stock to Compare...</option>
            {availableSymbols
              .filter(s => !comparisonData.some(c => c.symbol === s))
              .map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
          </select>
        </div>
      </div>

      {/* Comparison Grid Cards */}
      <div className="comparison-table-panel glass-panel rounded-3xl p-4 sm:p-5 border border-slate-800 overflow-x-auto">
        <table className="comparison-table w-full text-left text-xs font-mono">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider">
              <th className="py-4 px-4 sticky left-0 bg-slate-900 z-10 font-sans font-bold text-slate-300 min-w-[180px]">
                Fundamental Metric
              </th>
              {comparisonData.map(item => (
                <th key={item.symbol} className="py-4 px-6 text-center min-w-[200px] font-sans">
                  <div className="flex items-center justify-between gap-2 bg-slate-950 p-3 rounded-2xl border border-slate-800">
                    <div className="text-left cursor-pointer" onClick={() => onSelectStock(item.symbol)}>
                      <span className="font-extrabold text-base text-white hover:text-emerald-400 block">
                        {item.symbol}
                      </span>
                      <span className="text-[11px] text-slate-400 font-mono line-clamp-1">{item.name}</span>
                    </div>
                    <button
                      onClick={() => onRemoveSymbol(item.symbol)}
                      className="text-slate-500 hover:text-rose-400 p-1 rounded-lg hover:bg-slate-900 transition-colors"
                      title="Remove"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            
            {/* Verdict & Score */}
            <tr className="hover:bg-slate-900/50 bg-slate-900/20 font-bold">
              <td className="py-3 px-4 sticky left-0 bg-slate-900 font-sans text-emerald-400">
                Composite Score & Verdict
              </td>
              {comparisonData.map(item => (
                <td key={item.symbol} className="py-3 px-6 text-center">
                  {directionalValue('composite_score', item.composite_score, <strong>{item.composite_score}/100</strong>)}
                  <span className="text-[10px] text-slate-300 font-sans">{item.verdict}</span>
                </td>
              ))}
            </tr>

            {/* Current Price */}
            <tr className="hover:bg-slate-900/50">
              <td className="py-3 px-4 sticky left-0 bg-slate-950 font-sans text-slate-400">Current Price (₹)</td>
              {comparisonData.map(item => (
                <td key={item.symbol} className="py-3 px-6 text-center text-slate-100 font-bold">
                  {formatRupees(item.current_price)}
                </td>
              ))}
            </tr>

            {/* Market Cap */}
            <tr className="hover:bg-slate-900/50">
              <td className="py-3 px-4 sticky left-0 bg-slate-950 font-sans text-slate-400"><ConceptHelp term="market_cap" label="Market Cap (₹ Cr)" /></td>
              {comparisonData.map(item => (
                <td key={item.symbol} className="py-3 px-6 text-center text-slate-300">
                  {formatCrores(item.market_cap_cr)}
                </td>
              ))}
            </tr>

            {/* P/E Ratio */}
            <tr className="hover:bg-slate-900/50">
              <td className="py-3 px-4 sticky left-0 bg-slate-950 font-sans text-slate-400"><ConceptHelp term="pe" label="Stock P/E Multiple" /></td>
              {comparisonData.map(item => (
                <td key={item.symbol} className="py-3 px-6 text-center text-slate-200">
                  {formatMultiple(item.pe_ratio)}
                </td>
              ))}
            </tr>

            {/* ROCE */}
            <tr className="hover:bg-slate-900/50">
              <td className="py-3 px-4 sticky left-0 bg-slate-950 font-sans text-slate-400"><ConceptHelp term="roce" label="ROCE %" /></td>
              {comparisonData.map(item => (
                <td key={item.symbol} className="py-3 px-6 text-center font-bold">
                  {directionalValue('roce_pct', item.roce_pct, formatPercent(item.roce_pct))}
                </td>
              ))}
            </tr>

            {/* ROE */}
            <tr className="hover:bg-slate-900/50">
              <td className="py-3 px-4 sticky left-0 bg-slate-950 font-sans text-slate-400"><ConceptHelp term="roe" label="ROE %" /></td>
              {comparisonData.map(item => (
                <td key={item.symbol} className="py-3 px-6 text-center text-slate-300 font-semibold">
                  {formatPercent(item.roe_pct)}
                </td>
              ))}
            </tr>

            {/* FCF Yield */}
            <tr className="hover:bg-slate-900/50">
              <td className="py-3 px-4 sticky left-0 bg-slate-950 font-sans text-slate-400"><ConceptHelp term="fcf_yield" label="FCF Yield %" /></td>
              {comparisonData.map(item => (
                <td key={item.symbol} className="py-3 px-6 text-center font-bold">
                  {directionalValue('fcf_yield_pct', item.fcf_yield_pct, formatPercent(item.fcf_yield_pct))}
                </td>
              ))}
            </tr>

            {/* 3Y Sales CAGR */}
            <tr className="hover:bg-slate-900/50">
              <td className="py-3 px-4 sticky left-0 bg-slate-950 font-sans text-slate-400"><ConceptHelp term="sales_cagr" label="3Y Sales CAGR %" /></td>
              {comparisonData.map(item => (
                <td key={item.symbol} className="py-3 px-6 text-center text-slate-300">
                  {formatPercent(item.sales_cagr_3yr)}
                </td>
              ))}
            </tr>

            {/* 5Y CFO to PAT */}
            <tr className="hover:bg-slate-900/50">
              <td className="py-3 px-4 sticky left-0 bg-slate-950 font-sans text-slate-400"><ConceptHelp term="cfo_pat" label="5Y CFO / PAT Conversion" /></td>
              {comparisonData.map(item => (
                <td key={item.symbol} className="py-3 px-6 text-center font-semibold text-slate-300">
                  {formatPercent(item.cfo_to_pat_5yr)}
                </td>
              ))}
            </tr>

            {/* Debt to Equity */}
            <tr className="hover:bg-slate-900/50">
              <td className="py-3 px-4 sticky left-0 bg-slate-950 font-sans text-slate-400"><ConceptHelp term="debt_equity" label="Debt to Equity" /></td>
              {comparisonData.map(item => (
                <td key={item.symbol} className="py-3 px-6 text-center text-slate-300">
                  {directionalValue('debt_to_equity', item.debt_to_equity, formatMultiple(item.debt_to_equity))}
                </td>
              ))}
            </tr>

            {/* DCF Upside */}
            <tr className="hover:bg-slate-900/50 bg-slate-900/10">
              <td className="py-3 px-4 sticky left-0 bg-slate-900 font-sans font-semibold text-slate-200">
                <div className="flex items-center gap-2"><ConceptHelp term="dcf" label="DCF Fair Value Upside" /><DataOriginBadge origin="stocker_projection" compact /></div>
              </td>
              {comparisonData.map(item => (
                <td key={item.symbol} className={`py-3 px-6 text-center font-bold ${item.dcf_upside_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {item.dcf_upside_pct >= 0 ? `+${item.dcf_upside_pct}% ↑` : `${item.dcf_upside_pct}% ↓`}
                </td>
              ))}
            </tr>

            {/* Projected 3Y IRR */}
            <tr className="hover:bg-slate-900/50 bg-emerald-950/20 font-bold">
              <td className="py-3 px-4 sticky left-0 bg-emerald-950/80 font-sans text-emerald-300">
                <div className="flex items-center gap-2"><ConceptHelp term="irr" label="Projected 3-Year IRR %" /><DataOriginBadge origin="stocker_projection" compact /></div>
              </td>
              {comparisonData.map(item => (
                <td key={item.symbol} className={`py-3 px-6 text-center text-sm ${item.projected_3yr_irr_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {item.projected_3yr_irr_pct > 0 ? '+' : ''}{item.projected_3yr_irr_pct}% / yr {item.projected_3yr_irr_pct >= 0 ? '↑' : '↓'}
                </td>
              ))}
            </tr>

          </tbody>
        </table>
      </div>

      {/* Comparative Score Factor Breakdown Chart */}
      <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
        <div>
          <h3 className="text-base font-bold text-white">5-Pillar Score Factor Breakdown</h3>
          <p className="text-xs text-slate-400">Comparative assessment across growth, cash flow, capital efficiency, balance sheet safety, and valuation</p>
        </div>

        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={scoreChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
              <XAxis dataKey="symbol" stroke="var(--chart-axis)" fontSize={11} />
              <YAxis domain={[0, 100]} stroke="var(--chart-axis)" fontSize={11} tickFormatter={(value) => `${value}`} width={34} />
              <Tooltip 
                contentStyle={{ backgroundColor: 'var(--card-bg)', borderColor: 'var(--border-strong)', color: 'var(--text-primary)', borderRadius: '12px' }}
                labelStyle={{ color: 'var(--text-primary)', fontWeight: 700 }}
                cursor={{ fill: 'var(--hover-bg)' }}
                formatter={(value: any, name: string) => [`${value}/100`, name]}
              />
              <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
              <Bar dataKey="Growth" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Cash Quality" fill="#06b6d4" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Efficiency" fill="#6366f1" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Safety" fill="#f59e0b" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Valuation" fill="#ec4899" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

    </div>
  );
};
