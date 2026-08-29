import React, { useState } from 'react';
import { StockSummary } from '../types';
import { 
  Sparkles, Award, ArrowUpRight, TrendingUp, DollarSign, 
  Percent, Activity, CheckCircle2, ChevronRight, Filter, 
  ArrowUpDown, ArrowUp, ArrowDown, ExternalLink, Flame
} from 'lucide-react';
import { ConceptHelp } from './ui/ConceptHelp';

interface DashboardOverviewProps {
  stocks: StockSummary[];
  onSelectStock: (symbol: string) => void;
  selectedCompareSymbols: string[];
  onToggleCompare: (symbol: string) => void;
  onOpenCompare: () => void;
}

export const DashboardOverview: React.FC<DashboardOverviewProps> = ({
  stocks,
  onSelectStock,
  selectedCompareSymbols,
  onToggleCompare,
  onOpenCompare
}) => {
  const [selectedSector, setSelectedSector] = useState<string>('ALL');
  const [sortField, setSortField] = useState<keyof StockSummary>('composite_score');
  const [sortAsc, setSortAsc] = useState<boolean>(false);
  const [searchFilter, setSearchFilter] = useState<string>('');

  // Extract unique sectors
  const sectors = ['ALL', ...Array.from(new Set(stocks.map(s => s.sector)))];

  // Top 5 High-Conviction Bets
  const topPicks = stocks.filter(s => s.rank <= 5);

  // Filtered & Sorted Stocks for Table
  const filteredStocks = stocks
    .filter(s => {
      const matchesSector = selectedSector === 'ALL' || s.sector === selectedSector;
      const matchesSearch = s.symbol.toLowerCase().includes(searchFilter.toLowerCase()) || 
                            s.name.toLowerCase().includes(searchFilter.toLowerCase());
      return matchesSector && matchesSearch;
    })
    .sort((a, b) => {
      const valA = a[sortField];
      const valB = b[sortField];
      if (typeof valA === 'number' && typeof valB === 'number') {
        return sortAsc ? valA - valB : valB - valA;
      }
      if (typeof valA === 'string' && typeof valB === 'string') {
        return sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      return 0;
    });

  const handleSort = (field: keyof StockSummary) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  const getVerdictBadge = (verdict: string) => {
    switch (verdict) {
      case 'High Conviction Buy':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
      case 'Strong Growth Buy':
        return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40';
      case 'Fair Value Hold':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
      case 'Watchlist':
        return 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40';
      default:
        return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
    }
  };

  const getScoreBand = (verdict: string) => {
    if (verdict === 'High Conviction Buy' || verdict === 'Strong Growth Buy') return 'score-band-positive';
    if (verdict === 'Fair Value Hold') return 'score-band-warning';
    if (verdict === 'Watchlist') return 'score-band-neutral';
    return 'score-band-negative';
  };

  const sortIndicator = (field: keyof StockSummary) => {
    if (sortField !== field) return <ArrowUpDown className="w-3 h-3" aria-hidden="true" />;
    return sortAsc
      ? <ArrowUp className="w-3.5 h-3.5" aria-label="Sorted ascending" />
      : <ArrowDown className="w-3.5 h-3.5" aria-label="Sorted descending" />;
  };

  const sortHeaderClass = (field: keyof StockSummary) => `dashboard-sort-header ${sortField === field ? 'dashboard-sort-active' : ''}`;

  return (
    <div className="space-y-8 pb-16">
      
      {/* Top Banner & KPI Ribbon */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-slate-900/90 to-emerald-950/40 border border-slate-800 p-6 md:p-8 shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 max-w-3xl space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5" />
            <span>INSTITUTIONAL QUANTITATIVE & QUALITATIVE SCREENER</span>
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-white">
            High-Conviction Stock Picking <span className="bg-gradient-to-r from-emerald-400 to-teal-300 bg-clip-text text-transparent">Decision Engine</span>
          </h1>
          <p className="text-slate-300 text-sm md:text-base leading-relaxed">
            Raw Screener financial statements, QoQ/YoY operating leverage, free cashflow conversion, and concall guidance to uncover the highest quality long-term compounders.
          </p>
        </div>

        {/* Quick KPI Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-slate-800/80">
          <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800">
            <span className="text-xs text-slate-400 font-medium">Universe Size</span>
            <div className="text-xl font-bold text-white mt-0.5">{stocks.length} Companies</div>
            <span className="text-[11px] text-emerald-400 flex items-center gap-1 mt-1">
              <CheckCircle2 className="w-3 h-3" /> Nifty Leaders & Extended
            </span>
          </div>

          <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800">
            <span className="text-xs text-slate-400 font-medium">Top Conviction Ideas</span>
            <div className="text-xl font-bold text-emerald-400 mt-0.5">{topPicks.length} Stocks</div>
            <span className="text-[11px] text-slate-400 mt-1 block">Score &gt; 70.0 / 100</span>
          </div>

          <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800">
            <span className="text-xs text-slate-400 font-medium"><ConceptHelp term="roce" label="Highest ROCE In Group" /></span>
            <div className="text-xl font-bold text-primary mt-0.5">
              {Math.max(...stocks.map(s => s.roce_pct))}%
            </div>
            <span className="text-[11px] text-slate-400 mt-1 block">
              Highest reported · {stocks.find(s => s.roce_pct === Math.max(...stocks.map(x => x.roce_pct)))?.symbol}
            </span>
          </div>

          <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800">
            <span className="text-xs text-slate-400 font-medium"><ConceptHelp term="fcf" label="Top FCF Yield" /></span>
            <div className="text-xl font-bold text-primary mt-0.5">
              {Math.max(...stocks.map(s => s.fcf_yield_pct))}%
            </div>
            <span className="text-[11px] text-slate-400 mt-1 block">
              Highest reported · {stocks.find(s => s.fcf_yield_pct === Math.max(...stocks.map(x => x.fcf_yield_pct)))?.symbol}
            </span>
          </div>
        </div>
      </div>

      {/* TOP 5 HIGH CONVICTION BETS SPOTLIGHT */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30">
              <Flame className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white tracking-tight">Top 5 High-Conviction Bets</h2>
              <p className="text-xs text-slate-400">Selected based on Earnings Quality, FCF Generation, RoCE, and Margin of Safety</p>
            </div>
          </div>

          {selectedCompareSymbols.length > 1 && (
            <button
              onClick={onOpenCompare}
              className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold px-4 py-2 rounded-xl text-xs flex items-center gap-1.5 transition-colors shadow-lg shadow-emerald-500/20"
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Compare Selected ({selectedCompareSymbols.length})</span>
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {topPicks.map((stock) => (
            <div
              key={stock.symbol}
              className="glass-panel glass-card-hover rounded-2xl p-5 border border-slate-800 flex flex-col justify-between relative group cursor-pointer"
              onClick={() => onSelectStock(stock.symbol)}
            >
              <div className="space-y-4">
                {/* Header with Rank & Verdict */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <div className={`w-8 h-8 rounded-xl font-mono font-bold text-sm flex items-center justify-center shadow-md ${
                      stock.rank === 1 ? 'bg-gradient-to-br from-amber-400 to-amber-600 text-slate-950' :
                      stock.rank === 2 ? 'bg-gradient-to-br from-slate-200 to-slate-400 text-slate-950' :
                      stock.rank === 3 ? 'bg-gradient-to-br from-amber-700 to-amber-900 text-amber-100' :
                      'bg-slate-800 text-slate-300 border border-slate-700'
                    }`}>
                      #{stock.rank}
                    </div>
                    <div>
                      <h3 className="font-extrabold text-lg text-white group-hover:text-emerald-400 transition-colors flex items-center gap-1.5">
                        {stock.symbol}
                        <ArrowUpRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity text-emerald-400" />
                      </h3>
                      <p className="text-xs text-slate-400 line-clamp-1">{stock.name}</p>
                    </div>
                  </div>

                  <div className="flex flex-col items-end gap-1">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${getVerdictBadge(stock.verdict)}`}>
                      {stock.verdict}
                    </span>
                    <span className={`score-spotlight ${getScoreBand(stock.verdict)}`}>Score {stock.composite_score}/100</span>
                  </div>
                </div>

                {/* Key Fundamental Metric Chips */}
                <div className="grid grid-cols-3 gap-2 bg-slate-950/70 p-3 rounded-xl border border-slate-800/80 text-center font-mono">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase block font-sans">P/E</span>
                    <span className="text-xs font-semibold text-slate-200">{stock.pe_ratio}x</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase block font-sans">ROCE</span>
                    <span className="text-xs font-semibold text-slate-200">{stock.roce_pct}%</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase block font-sans">FCF Yield</span>
                    <span className="text-xs font-semibold text-slate-200">{stock.fcf_yield_pct}%</span>
                  </div>
                </div>

                {/* Investment Thesis Snippet */}
                <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800/50">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                    Investment Thesis
                  </span>
                  <p className="text-xs text-slate-300 line-clamp-3 leading-relaxed">
                    {stock.investment_thesis_short}
                  </p>
                </div>
              </div>

              {/* Action Footer */}
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between">
                <label 
                  className="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer hover:text-slate-200"
                  onClick={(e) => e.stopPropagation()}
                >
                  <input
                    type="checkbox"
                    checked={selectedCompareSymbols.includes(stock.symbol)}
                    onChange={() => onToggleCompare(stock.symbol)}
                    className="rounded border-slate-700 text-emerald-500 focus:ring-emerald-500/30 bg-slate-900 w-3.5 h-3.5"
                  />
                  <span>Select to Compare</span>
                </label>

                <button 
                  onClick={() => onSelectStock(stock.symbol)}
                  className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 flex items-center gap-1"
                >
                  <span>Deep Dive</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ALL TRACKED STOCKS SCREENER & RANKING TABLE */}
      <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-6">
        
        {/* Table Controls: Sector Filters & Search */}
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">Stock Universe & Screener Matrix</h2>
            <p className="text-xs text-slate-400">Click headers to sort across fundamental indicators and cash conversion metrics</p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <input
                type="text"
                placeholder="Filter table..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                className="bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 w-44"
              />
            </div>

            {/* Sector Selector */}
            <div className="flex items-center gap-1 overflow-x-auto max-w-full pb-1">
              {sectors.slice(0, 6).map((sec) => (
                <button
                  key={sec}
                  onClick={() => setSelectedSector(sec)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors ${
                    selectedSector === sec
                      ? 'bg-slate-800 text-emerald-400 border border-emerald-500/30 shadow-sm'
                      : 'bg-slate-900/80 text-slate-400 hover:text-slate-200 border border-slate-800'
                  }`}
                >
                  {sec}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* High-Density Data Table */}
        <div className="dashboard-table-wrap overflow-x-auto rounded-2xl border border-slate-800">
          <table className="dashboard-table w-full text-left text-xs">
            <thead className="bg-slate-900/90 text-slate-400 font-mono uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="dashboard-compare-col py-3.5 px-4 w-12 text-center">Compare</th>
                <th className={`${sortHeaderClass('symbol')} dashboard-company-col`} onClick={() => handleSort('symbol')} aria-sort={sortField === 'symbol' ? (sortAsc ? 'ascending' : 'descending') : 'none'}>
                  <div className="flex items-center gap-1">
                    <span>Company</span>
                    {sortIndicator('symbol')}
                  </div>
                </th>
                <th className={sortHeaderClass('rank')} onClick={() => handleSort('rank')} aria-sort={sortField === 'rank' ? (sortAsc ? 'ascending' : 'descending') : 'none'}>
                  <div className="flex items-center gap-1">
                    <span>Rank</span>
                    {sortIndicator('rank')}
                  </div>
                </th>
                <th className={sortHeaderClass('current_price')} onClick={() => handleSort('current_price')} aria-sort={sortField === 'current_price' ? (sortAsc ? 'ascending' : 'descending') : 'none'}>
                  <div className="flex items-center gap-1">
                    <span>Price (₹)</span>
                    {sortIndicator('current_price')}
                  </div>
                </th>
                <th className={sortHeaderClass('pe_ratio')} onClick={() => handleSort('pe_ratio')} aria-sort={sortField === 'pe_ratio' ? (sortAsc ? 'ascending' : 'descending') : 'none'}>
                  <div className="flex items-center gap-1">
                    <ConceptHelp term="pe" label="P/E" />
                    {sortIndicator('pe_ratio')}
                  </div>
                </th>
                <th className={sortHeaderClass('roce_pct')} onClick={() => handleSort('roce_pct')} aria-sort={sortField === 'roce_pct' ? (sortAsc ? 'ascending' : 'descending') : 'none'}>
                  <div className="flex items-center gap-1">
                    <ConceptHelp term="roce" label="ROCE %" />
                    {sortIndicator('roce_pct')}
                  </div>
                </th>
                <th className={sortHeaderClass('roe_pct')} onClick={() => handleSort('roe_pct')} aria-sort={sortField === 'roe_pct' ? (sortAsc ? 'ascending' : 'descending') : 'none'}>
                  <div className="flex items-center gap-1">
                    <ConceptHelp term="roe" label="ROE %" />
                    {sortIndicator('roe_pct')}
                  </div>
                </th>
                <th className={sortHeaderClass('fcf_yield_pct')} onClick={() => handleSort('fcf_yield_pct')} aria-sort={sortField === 'fcf_yield_pct' ? (sortAsc ? 'ascending' : 'descending') : 'none'}>
                  <div className="flex items-center gap-1">
                    <ConceptHelp term="fcf" label="FCF Yield" />
                    {sortIndicator('fcf_yield_pct')}
                  </div>
                </th>
                <th className={sortHeaderClass('sales_growth_3yr_pct')} onClick={() => handleSort('sales_growth_3yr_pct')} aria-sort={sortField === 'sales_growth_3yr_pct' ? (sortAsc ? 'ascending' : 'descending') : 'none'}>
                  <div className="flex items-center gap-1">
                    <ConceptHelp term="sales_cagr" label="3Y Sales CAGR" />
                    {sortIndicator('sales_growth_3yr_pct')}
                  </div>
                </th>
                <th className={sortHeaderClass('cfo_to_pat_5yr_pct')} onClick={() => handleSort('cfo_to_pat_5yr_pct')} aria-sort={sortField === 'cfo_to_pat_5yr_pct' ? (sortAsc ? 'ascending' : 'descending') : 'none'}>
                  <div className="flex items-center gap-1">
                    <ConceptHelp term="cfo_pat" label="CFO/PAT (5Y)" />
                    {sortIndicator('cfo_to_pat_5yr_pct')}
                  </div>
                </th>
                <th className={sortHeaderClass('net_debt_to_equity')} onClick={() => handleSort('net_debt_to_equity')} aria-sort={sortField === 'net_debt_to_equity' ? (sortAsc ? 'ascending' : 'descending') : 'none'}>
                  <div className="flex items-center gap-1">
                    <ConceptHelp term="debt_equity" label="Debt/Eq" />
                    {sortIndicator('net_debt_to_equity')}
                  </div>
                </th>
                <th className={sortHeaderClass('composite_score')} onClick={() => handleSort('composite_score')} aria-sort={sortField === 'composite_score' ? (sortAsc ? 'ascending' : 'descending') : 'none'}>
                  <div className="flex items-center gap-1">
                    <span>Composite Score</span>
                    {sortIndicator('composite_score')}
                  </div>
                </th>
                <th className="py-3.5 px-4">Verdict</th>
                <th className="py-3.5 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {filteredStocks.map((stock) => {
                const isSelected = selectedCompareSymbols.includes(stock.symbol);
                return (
                <tr 
                  key={stock.symbol}
                  className={`dashboard-row hover:bg-slate-900/50 transition-colors group cursor-pointer ${isSelected ? 'dashboard-row-selected' : ''}`}
                  onClick={() => onSelectStock(stock.symbol)}
                >
                  <td className="dashboard-compare-col py-3.5 px-4 text-center" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => onToggleCompare(stock.symbol)}
                      aria-label={`${isSelected ? 'Remove' : 'Add'} ${stock.symbol} ${isSelected ? 'from' : 'to'} comparison`}
                      className="rounded border-slate-700 text-emerald-500 focus:ring-emerald-500/30 bg-slate-900 w-3.5 h-3.5"
                    />
                  </td>
                  <td className="dashboard-company-col py-3.5 px-4 font-sans">
                    <div className="font-bold text-white group-hover:text-emerald-400 transition-colors">
                      {stock.symbol}
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono">{stock.sector}</div>
                  </td>
                  <td className="py-3.5 px-4 font-bold text-slate-300">
                    <span className="rank-pill">#{stock.rank}</span>
                  </td>
                  <td className="py-3.5 px-4 text-slate-100 font-semibold">
                    ₹{stock.current_price.toLocaleString('en-IN')}
                  </td>
                  <td className="py-3.5 px-4 text-slate-300">
                    {stock.pe_ratio}x
                  </td>
                  <td className="py-3.5 px-4 font-semibold text-slate-300">
                    {stock.roce_pct}%
                  </td>
                  <td className="py-3.5 px-4 text-slate-300">
                    {stock.roe_pct}%
                  </td>
                  <td className="py-3.5 px-4 font-semibold text-slate-300">
                    {stock.fcf_yield_pct}%
                  </td>
                  <td className="py-3.5 px-4 text-slate-300">
                    {stock.sales_growth_3yr_pct}%
                  </td>
                  <td className={`py-3.5 px-4 ${stock.cfo_to_pat_5yr_pct >= 90 ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {stock.cfo_to_pat_5yr_pct}%
                  </td>
                  <td className="py-3.5 px-4 text-slate-300">
                    {stock.net_debt_to_equity}x
                  </td>
                  <td className="py-3.5 px-4">
                    <div className={`dashboard-score-cell ${getScoreBand(stock.verdict)}`}>
                      <strong>{stock.composite_score}</strong><span>/100</span>
                      <i aria-hidden="true"><b style={{ width: `${Math.max(0, Math.min(100, stock.composite_score))}%` }} /></i>
                    </div>
                  </td>
                  <td className="py-3.5 px-4 font-sans">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border whitespace-nowrap ${getVerdictBadge(stock.verdict)}`}>
                      {stock.verdict}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-right font-sans">
                    <button
                      onClick={() => onSelectStock(stock.symbol)}
                      className="bg-slate-800 hover:bg-emerald-600 hover:text-white text-slate-300 px-3 py-1 rounded-lg text-xs font-semibold transition-colors"
                    >
                      Dossier
                    </button>
                  </td>
                </tr>
              );})}
            </tbody>
          </table>
        </div>

      </div>

    </div>
  );
};
