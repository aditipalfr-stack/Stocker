import React from 'react';
import { TrendingUp, BarChart2, ShieldCheck, Layers, BookOpen, Moon, Sun, Sparkles } from 'lucide-react';
import { useTheme } from '../theme/ThemeProvider';
import { useAnalysisJobs } from '../context/AnalysisJobContext';
import { CompanySearchAdd } from './CompanySearchAdd';

interface NavbarProps {
  activeTab: 'overview' | 'detail' | 'compare';
  setActiveTab: (tab: 'overview' | 'detail' | 'compare') => void;
  onAddCompany: (query: string) => Promise<void>;
  onOpenExisting: (symbol: string) => Promise<void>;
  isLoading: boolean;
  selectedStockSymbol?: string;
  compareCount: number;
  onOpenGlossary: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  onAddCompany,
  onOpenExisting,
  isLoading,
  selectedStockSymbol,
  compareCount,
  onOpenGlossary
}) => {
  const { theme, toggleTheme } = useTheme();
  const { activeJobs } = useAnalysisJobs();

  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-slate-800/80 py-3.5">
      <div className="layout-wide navbar-layout flex flex-col md:flex-row md:flex-wrap items-center justify-between gap-4">
        
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

        <CompanySearchAdd disabled={isLoading} onAdd={onAddCompany} onOpenExisting={onOpenExisting} />

        {/* Navigation Tabs */}
        <div className="navbar-actions flex items-center justify-start md:justify-center gap-1.5 bg-slate-900/80 p-1 rounded-xl border border-slate-800 overflow-x-auto max-w-full w-full 2xl:w-auto">
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

          {activeJobs.length > 0 && (
            <button
              type="button"
              onClick={() => onOpenExisting(activeJobs[0].symbol)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/25 transition-all shadow-sm shadow-indigo-500/20 animate-pulse"
              title={`${activeJobs[0].stage_message} (${activeJobs[0].progress_pct}%)`}
            >
              <Sparkles className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
              <span>Analyzing {activeJobs[0].symbol} ({activeJobs[0].progress_pct}%)</span>
            </button>
          )}

          <div className="w-px h-5 bg-slate-800 mx-0.5 shrink-0" aria-hidden="true" />

          <button type="button" onClick={onOpenGlossary} className="nav-utility-button" title="Open investor glossary">
            <BookOpen className="w-3.5 h-3.5" />
            <span>Glossary</span>
          </button>

          <button
            type="button"
            onClick={toggleTheme}
            className="nav-utility-button"
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {theme === 'dark' ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
            <span>{theme === 'dark' ? 'Light' : 'Dark'}</span>
          </button>
        </div>

      </div>
    </header>
  );
};
