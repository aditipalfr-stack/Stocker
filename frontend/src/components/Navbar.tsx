import React, { useState } from 'react';
import { TrendingUp, Search, PlusCircle, RefreshCw, BarChart2, ShieldCheck, Layers } from 'lucide-react';

interface NavbarProps {
  activeTab: 'overview' | 'detail' | 'compare';
  setActiveTab: (tab: 'overview' | 'detail' | 'compare') => void;
  onSearchOrScrape: (symbol: string) => Promise<void>;
  isLoading: boolean;
  selectedStockSymbol?: string;
  compareCount: number;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  onSearchOrScrape,
  isLoading,
  selectedStockSymbol,
  compareCount
}) => {
  const [searchInput, setSearchInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchInput.trim()) return;
    setIsSubmitting(true);
    try {
      await onSearchOrScrape(searchInput.trim().toUpperCase());
      setSearchInput('');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-slate-800/80 px-4 lg:px-8 py-3.5">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        
        {/* Brand Logo & Title */}
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => setActiveTab('overview')}>
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 via-teal-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <TrendingUp className="w-6 h-6 text-slate-950 font-bold stroke-[2.5]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-xl tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                STOCKER
              </span>
              <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                NIFTY 500
              </span>
            </div>
            <p className="text-xs text-slate-400 font-medium">Fundamental Screener & Decision Engine</p>
          </div>
        </div>

        {/* Live Search & On-Demand Screener Ingestion Bar */}
        <form onSubmit={handleSearchSubmit} className="flex items-center w-full md:w-auto relative">
          <div className="relative w-full md:w-80">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search or add ticker (e.g. TITAN, DIXON)..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl pl-9 pr-24 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all font-mono"
            />
            <button
              type="submit"
              disabled={isSubmitting || !searchInput.trim()}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold px-2.5 py-1 rounded-lg transition-colors flex items-center gap-1 shadow-sm"
            >
              {isSubmitting ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <PlusCircle className="w-3.5 h-3.5" />
              )}
              <span>Add</span>
            </button>
          </div>
        </form>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-2 bg-slate-900/80 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab('overview')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeTab === 'overview'
                ? 'bg-emerald-500 text-slate-950 font-bold shadow-md shadow-emerald-500/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Leaderboard & Top Bets</span>
          </button>

          {selectedStockSymbol && (
            <button
              onClick={() => setActiveTab('detail')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === 'detail'
                  ? 'bg-emerald-500 text-slate-950 font-bold shadow-md shadow-emerald-500/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <BarChart2 className="w-3.5 h-3.5" />
              <span>{selectedStockSymbol} Dossier</span>
            </button>
          )}

          <button
            onClick={() => setActiveTab('compare')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeTab === 'compare'
                ? 'bg-emerald-500 text-slate-950 font-bold shadow-md shadow-emerald-500/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Compare {compareCount > 0 ? `(${compareCount})` : ''}</span>
          </button>
        </div>

      </div>
    </header>
  );
};

