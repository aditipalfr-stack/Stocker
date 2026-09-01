import React from 'react';
import { AlertTriangle, CheckCircle2, Circle, RefreshCw, Search, Sparkles } from 'lucide-react';
import type { ResearchLifecycleStatus } from '../types';
import type { GlossaryTerm } from '../data/glossary';
import { ConceptHelp } from './ui/ConceptHelp';

export type BackgroundResearchState = 'idle' | 'running' | 'success' | 'error';

interface ResearchStatusPanelProps {
  status: ResearchLifecycleStatus | null;
  loading?: boolean;
  error?: string | null;
  filingDiscoveryState?: BackgroundResearchState;
  verificationState?: BackgroundResearchState;
  businessAnalysisRunning?: boolean;
  onRetryStatus?: () => void;
  onRetryFilings?: () => void;
  onRetryVerification?: () => void;
  onRunAnalysis?: () => void;
}

interface StageDisplay {
  title: string;
  label: string;
  detail?: string;
  tone: 'ready' | 'pending' | 'warning' | 'running';
  action?: React.ReactNode;
  concept?: GlossaryTerm;
}

const StatusIcon = ({ tone }: { tone: StageDisplay['tone'] }) => {
  if (tone === 'running') return <RefreshCw className="w-4 h-4 text-cyan-400 animate-spin" aria-hidden="true" />;
  if (tone === 'ready') return <CheckCircle2 className="w-4 h-4 text-emerald-400" aria-hidden="true" />;
  if (tone === 'warning') return <AlertTriangle className="w-4 h-4 text-amber-400" aria-hidden="true" />;
  return <Circle className="w-4 h-4 text-slate-500" aria-hidden="true" />;
};

export const ResearchStatusPanel: React.FC<ResearchStatusPanelProps> = ({
  status,
  loading,
  error,
  filingDiscoveryState = 'idle',
  verificationState = 'idle',
  businessAnalysisRunning,
  onRetryStatus,
  onRetryFilings,
  onRetryVerification,
  onRunAnalysis
}) => {
  if (!status) {
    return (
      <section className="glass-panel rounded-3xl border border-slate-800 p-5" aria-labelledby="research-progress-title">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 id="research-progress-title" className="text-sm font-bold text-white">Research progress</h3>
            <p className="text-xs text-slate-400 mt-1">
              {loading ? 'Loading the latest research lifecycle…' : error || 'Research lifecycle status is not available yet.'}
            </p>
          </div>
          {loading ? <RefreshCw className="w-4 h-4 text-cyan-400 animate-spin" /> : onRetryStatus && (
            <button onClick={onRetryStatus} className="text-xs text-cyan-300 border border-cyan-800 rounded-xl px-3 py-1.5">Retry</button>
          )}
        </div>
      </section>
    );
  }

  const stages: StageDisplay[] = [
    {
      title: 'Financial Data',
      label: status.financial_data === 'ready' ? 'Ready' : status.financial_data === 'stale' ? 'Refresh recommended' : status.financial_data === 'error' ? 'Ingestion error' : 'Not available',
      tone: status.financial_data === 'ready' ? 'ready' : status.financial_data === 'stale' ? 'warning' : 'pending',
      concept: status.financial_data === 'ready' ? 'standardized' : status.financial_data === 'stale' ? 'stale' : 'unavailable'
    },
    {
      title: 'Deterministic Analysis',
      label: status.deterministic_analysis === 'ready' ? 'Ready' : 'Waiting for financial data',
      tone: status.deterministic_analysis === 'ready' ? 'ready' : 'pending',
      concept: status.deterministic_analysis === 'ready' ? 'stocker_calculation' : 'unavailable'
    },
    {
      title: 'Official Verification',
      label: verificationState === 'running' ? 'Checking official figures…' : verificationState === 'error' ? 'Verification could not complete' : status.official_verification === 'verified' ? 'Verified' : status.official_verification === 'discrepancy' ? 'Discrepancy found' : status.official_verification === 'partial' ? 'Partially checked' : 'Not checked',
      tone: verificationState === 'running' ? 'running' : verificationState === 'error' || status.official_verification === 'discrepancy' ? 'warning' : status.official_verification === 'verified' ? 'ready' : 'pending',
      action: verificationState === 'error' && onRetryVerification ? <button onClick={onRetryVerification} className="text-[11px] text-cyan-300 hover:text-cyan-200">Retry</button> : undefined,
      concept: verificationState === 'error' ? 'unavailable' : status.official_verification === 'verified' ? 'verified' : status.official_verification === 'discrepancy' ? 'discrepancy' : status.official_verification === 'not_run' ? 'not_run' : 'standardized'
    },
    {
      title: 'Source Filings',
      label: filingDiscoveryState === 'running' ? 'Searching…' : filingDiscoveryState === 'error' ? 'Discovery could not complete' : status.source_filings === 'ready' ? `${status.filing_count} filing${status.filing_count === 1 ? '' : 's'} found` : status.source_filings === 'partial' ? `${status.filing_count} filing${status.filing_count === 1 ? '' : 's'} found — search incomplete` : status.source_filings === 'error' ? 'Discovery error' : 'Not searched',
      tone: filingDiscoveryState === 'running' ? 'running' : filingDiscoveryState === 'error' || status.source_filings === 'error' ? 'warning' : status.source_filings === 'ready' ? 'ready' : 'pending',
      action: (filingDiscoveryState === 'error' || status.source_filings === 'error') && onRetryFilings ? <button onClick={onRetryFilings} className="text-[11px] text-cyan-300 hover:text-cyan-200">Retry</button> : undefined,
      concept: status.source_filings === 'not_searched' ? 'not_run' : status.source_filings === 'error' ? 'unavailable' : undefined
    },
    {
      title: 'Business Analysis',
      label: businessAnalysisRunning || status.business_analysis === 'running' ? 'Analyzing filings…' : status.business_analysis === 'ready' ? 'Ready' : status.business_analysis === 'stale' ? 'Needs refresh' : status.business_analysis === 'error' ? 'Analysis error' : 'Not run',
      tone: businessAnalysisRunning || status.business_analysis === 'running' ? 'running' : status.business_analysis === 'ready' ? 'ready' : status.business_analysis === 'stale' || status.business_analysis === 'error' ? 'warning' : 'pending',
      action: status.business_analysis !== 'ready' && !businessAnalysisRunning && onRunAnalysis ? <button onClick={onRunAnalysis} className="text-[11px] text-emerald-300 hover:text-emerald-200 flex items-center gap-1"><Sparkles className="w-3 h-3" /> Run Analysis</button> : undefined,
      concept: status.business_analysis === 'not_run' ? 'not_run' : status.business_analysis === 'stale' ? 'stale' : status.business_analysis === 'ready' ? 'ai_interpretation' : status.business_analysis === 'error' ? 'unavailable' : undefined
    },
    {
      title: 'Projection',
      label: status.projection === 'historical_only' ? 'Preliminary — historical data only' : status.projection === 'evidence_enriched' ? 'Evidence-enriched' : status.projection === 'stale' ? 'Needs refresh' : 'Not available',
      detail: status.projection === 'stale' ? 'Business evidence changed.' : undefined,
      tone: status.projection === 'evidence_enriched' ? 'ready' : status.projection === 'stale' ? 'warning' : 'pending',
      concept: status.projection === 'evidence_enriched' ? 'evidence_enriched' : status.projection === 'stale' ? 'stale' : status.projection === 'unavailable' ? 'unavailable' : 'provisional'
    },
    {
      title: 'Investment Score',
      label: status.investment_score === 'provisional' ? 'Provisional — financial analysis only' : status.investment_score === 'evidence_enriched' ? 'Evidence-enriched' : status.investment_score === 'incomplete' ? 'Incomplete research' : 'Not available',
      tone: status.investment_score === 'evidence_enriched' ? 'ready' : status.investment_score === 'incomplete' ? 'warning' : 'pending',
      concept: status.investment_score === 'evidence_enriched' ? 'evidence_enriched' : status.investment_score === 'unavailable' || status.investment_score === 'incomplete' ? 'unavailable' : 'provisional'
    }
  ];

  return (
    <section className="glass-panel rounded-3xl border border-slate-800 p-5 space-y-4" aria-labelledby="research-progress-title">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 id="research-progress-title" className="text-sm font-bold text-white flex items-center gap-2"><Search className="w-4 h-4 text-cyan-400" /> Research progress</h3>
          <p className="text-[11px] text-slate-400 mt-1">Financial analysis is usable now; filing and AI research are separate stages.</p>
        </div>
        <span className="text-[10px] text-slate-400 border border-slate-800 rounded-full px-2.5 py-1">
          Identity: {status.identity === 'officially_verified' ? 'Officially verified' : status.identity === 'resolved' ? 'Resolved' : 'Unresolved'}
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-2.5">
        {stages.map(stage => (
          <div key={stage.title} className="bg-slate-950/60 border border-slate-800 rounded-2xl p-3 flex items-start gap-2.5 min-h-[76px]">
            <StatusIcon tone={stage.tone} />
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">{stage.title}</p>
              <p className="text-xs text-slate-200 mt-1 leading-snug">{stage.concept ? <ConceptHelp term={stage.concept} label={stage.label} /> : stage.label}</p>
              {stage.detail && <p className="text-[10px] text-amber-300 mt-1">{stage.detail}</p>}
              {stage.action && <div className="mt-1.5">{stage.action}</div>}
            </div>
          </div>
        ))}
      </div>
      {status.notes && status.notes.length > 0 && <p className="text-[11px] text-slate-400">{status.notes[0]}</p>}
      {error && (
        <div className="flex items-center justify-between gap-3 text-[11px] text-amber-200 bg-amber-950/20 border border-amber-800/40 rounded-xl px-3 py-2">
          <span>Latest lifecycle refresh failed. The last known status remains visible.</span>
          {onRetryStatus && <button onClick={onRetryStatus} className="text-cyan-300 hover:text-cyan-200 shrink-0">Retry status</button>}
        </div>
      )}
    </section>
  );
};
