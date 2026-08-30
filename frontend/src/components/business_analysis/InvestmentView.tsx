import React from 'react';
import { BusinessAnalysisIntelligence } from '../../types';
import { 
  Sparkles, CheckCircle2, AlertTriangle, Clock, 
  ArrowUpRight, ExternalLink, ShieldCheck, Target, Layers
} from 'lucide-react';
import { ConceptHelp } from '../ui/ConceptHelp';
import { DataOriginBadge } from '../ui/DataOriginBadge';

interface InvestmentViewProps {
  docIntel: BusinessAnalysisIntelligence;
  companyName: string;
}

export const InvestmentView: React.FC<InvestmentViewProps> = ({ docIntel, companyName }) => {
  const stockerView = docIntel.stocker_view;
  const recentChanges = docIntel.what_changed_recently || [];
  const risksAndCash = docIntel.risks_and_cash;

  const verdict = stockerView?.execution_verdict || 'Evolving / Watchlist';
  const verdictBg = 
    verdict === 'Strong Execution' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' :
    verdict === 'Mixed Execution' ? 'bg-amber-500/10 text-amber-400 border-amber-500/30' :
    verdict === 'Weak Execution' ? 'bg-rose-500/10 text-rose-400 border-rose-500/30' :
    'bg-cyan-500/10 text-cyan-400 border-cyan-500/30';

  return (
    <div className="space-y-6">
      
      {/* 1. Executive Summary & Verdict Hero */}
      <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-5 bg-gradient-to-br from-slate-900/90 via-slate-950 to-slate-900/60 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-base font-bold text-white flex items-center gap-2">
                <span>Executive Fundamental Thesis & Outlook</span>
                <DataOriginBadge origin="ai_interpretation" />
              </h4>
              <p className="text-xs text-slate-400">Institutional synthesis across official filings & audited statements</p>
            </div>
          </div>
          <div className="flex items-center gap-2 self-start sm:self-center">
            <span className="text-xs text-slate-400">Management Execution:</span>
            <span className={`text-xs font-bold px-3 py-1 rounded-full border ${verdictBg} flex items-center gap-1.5`}>
              <ShieldCheck className="w-3.5 h-3.5" />
              {verdict}
            </span>
          </div>
        </div>

        <p className="text-sm text-slate-200 leading-relaxed font-normal bg-slate-950/60 p-4 rounded-2xl border border-slate-800/80">
          {stockerView?.investor_summary || `Management execution is actively tracking across key milestones based on verified official filings and audited financials for ${companyName}.`}
        </p>

        {/* 3 Pillars Grid: Positives, Risks, What to Watch Next */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          
          {/* Key Positives & Triggers */}
          <div className="bg-emerald-950/20 border border-emerald-800/40 rounded-2xl p-4 space-y-3">
            <div className="flex items-center gap-2 text-emerald-400 text-xs font-bold uppercase tracking-wider">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Key Growth Positives</span>
            </div>
            <ul className="space-y-2 text-xs text-slate-300">
              {stockerView?.positive_triggers && stockerView.positive_triggers.length > 0 ? (
                stockerView.positive_triggers.map((pos, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0 mt-1.5" />
                    <span>{pos}</span>
                  </li>
                ))
              ) : (
                <li className="text-slate-400 italic">No specific positive triggers highlighted.</li>
              )}
            </ul>
          </div>

          {/* Key Risks & Headwinds */}
          <div className="bg-rose-950/20 border border-rose-800/40 rounded-2xl p-4 space-y-3">
            <div className="flex items-center gap-2 text-rose-400 text-xs font-bold uppercase tracking-wider">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>Critical Risks to Monitor</span>
            </div>
            <ul className="space-y-2 text-xs text-slate-300">
              {stockerView?.main_risks && stockerView.main_risks.length > 0 ? (
                stockerView.main_risks.map((risk, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-400 shrink-0 mt-1.5" />
                    <span>{risk}</span>
                  </li>
                ))
              ) : (
                <li className="text-slate-400 italic">No critical operational risks flagged.</li>
              )}
            </ul>
          </div>

          {/* What to Watch Next */}
          <div className="bg-cyan-950/20 border border-cyan-800/40 rounded-2xl p-4 space-y-3">
            <div className="flex items-center gap-2 text-cyan-400 text-xs font-bold uppercase tracking-wider">
              <Target className="w-4 h-4 text-cyan-400 shrink-0" />
              <span>Watch Next (2–4 Quarters)</span>
            </div>
            <ul className="space-y-2 text-xs text-slate-300">
              {stockerView?.what_to_watch_next && stockerView.what_to_watch_next.length > 0 ? (
                stockerView.what_to_watch_next.map((watch, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0 mt-1.5" />
                    <span>{watch}</span>
                  </li>
                ))
              ) : (
                <li className="text-slate-400 italic">Watch upcoming quarterly revenue run-rate and capacity commissioning.</li>
              )}
            </ul>
          </div>

        </div>
      </div>

      {/* 2. What Changed Recently */}
      <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-5">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-cyan-500/20 text-cyan-400 flex items-center justify-center border border-cyan-500/30">
              <Clock className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white flex items-center gap-2">
                <span>What Changed Recently</span>
                <span className="bg-slate-900 text-cyan-400 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-slate-800">
                  {recentChanges.length} developments
                </span>
              </h4>
              <p className="text-xs text-slate-400">Recent strategic, capex, pricing, and operational shifts across latest filings</p>
            </div>
          </div>
        </div>

        {recentChanges.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {recentChanges.map((change, idx) => (
              <div key={idx} className="bg-slate-950 p-5 rounded-2xl border border-slate-800/80 space-y-3 hover:border-slate-700 transition-all">
                <div className="flex items-start justify-between gap-3">
                  <span className="bg-cyan-500/10 text-cyan-400 text-[11px] font-semibold px-2.5 py-0.5 rounded-full border border-cyan-500/20">
                    {change.category || 'Strategic Shift'}
                  </span>
                  {change.source_url && (
                    <a
                      href={change.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] text-slate-400 hover:text-cyan-400 flex items-center gap-1 transition-colors"
                      title={change.source_doc || 'Source Filing'}
                    >
                      <span className="truncate max-w-[140px]">{change.source_doc || 'Filing'}</span>
                      {change.source_page && <span className="font-mono text-cyan-400">p.{change.source_page}</span>}
                      <ExternalLink className="w-3 h-3 shrink-0" />
                    </a>
                  )}
                </div>

                <div>
                  <h5 className="text-sm font-bold text-white leading-snug">{change.headline}</h5>
                  <p className="text-xs text-slate-300 mt-1 leading-relaxed">{change.detail}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-slate-950/60 p-6 rounded-2xl border border-slate-800 text-center text-xs text-slate-400">
            No recent structural changes extracted yet. Run live AI analysis to scan latest filings.
          </div>
        )}
      </div>

      {/* 3. Reported Financial Numbers Reality Cross-Check */}
      {risksAndCash?.reported_numbers_comparison && (
        <div className="bg-slate-950 p-5 md:p-6 rounded-3xl border border-cyan-800/40 bg-gradient-to-r from-slate-950 via-cyan-950/20 to-slate-950 space-y-2">
          <div className="flex items-center gap-2 text-cyan-400 text-xs font-bold uppercase tracking-wider">
            <ShieldCheck className="w-4 h-4 text-cyan-400 shrink-0" />
            <span>Deterministic Statement Cross-Check</span>
          </div>
          <p className="text-xs text-slate-200 leading-relaxed font-mono">
            {risksAndCash.reported_numbers_comparison}
          </p>
        </div>
      )}

    </div>
  );
};
