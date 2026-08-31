import React, { useState, useEffect, useCallback, useRef } from 'react';
import { StockDetail, BusinessAnalysisIntelligence, ResearchLifecycleStatus, SourceFilingsResponse } from '../../types';
import { AiStatusResult, fetchSourceFilings } from '../../api';
import type { BackgroundResearchState } from '../ResearchStatusPanel';
import { 
  Sparkles, TrendingUp, CheckCircle2, FileText, 
  Compass, Clock, AlertTriangle, KeyRound, Zap, HelpCircle, RefreshCw
} from 'lucide-react';
import { ConceptHelp } from '../ui/ConceptHelp';
import { DataOriginBadge } from '../ui/DataOriginBadge';
import { InvestmentView } from './InvestmentView';
import { BusinessGrowthView } from './BusinessGrowthView';
import { ManagementExecutionView } from './ManagementExecutionView';
import { SourceFilingsView } from './SourceFilingsView';

interface BusinessAnalysisViewProps {
  stock: StockDetail;
  docIntel: BusinessAnalysisIntelligence | null;
  loadingDocIntel: boolean;
  docIntelError: string | null;
  generatingDocIntel: boolean;
  aiStatus: AiStatusResult | null;
  researchStatus: ResearchLifecycleStatus | null;
  filingDiscoveryState: BackgroundResearchState;
  filingDiscoveryRevision: number;
  onGenerateIntel: () => void;
  onOpenKeyModal: () => void;
}

export const BusinessAnalysisView: React.FC<BusinessAnalysisViewProps> = ({
  stock,
  docIntel,
  loadingDocIntel,
  docIntelError,
  generatingDocIntel,
  aiStatus,
  researchStatus,
  filingDiscoveryState,
  filingDiscoveryRevision,
  onGenerateIntel,
  onOpenKeyModal
}) => {
  const [activeSubTab, setActiveSubTab] = useState<'investment' | 'growth' | 'management' | 'filings'>('investment');

  // Source Filings cache lifted to parent container to persist across tab switches
  const [filingsCache, setFilingsCache] = useState<Record<string, { data: SourceFilingsResponse; revision: number }>>({});
  const [filingsLoading, setFilingsLoading] = useState<boolean>(false);
  const [filingsError, setFilingsError] = useState<string | null>(null);
  const filingRevisionRef = useRef(filingDiscoveryRevision);
  const filingRequestIdRef = useRef(0);
  filingRevisionRef.current = filingDiscoveryRevision;

  const loadSourceFilings = useCallback(async (targetSymbol: string, force: boolean = false) => {
    const cached = filingsCache[targetSymbol];
    if (!force && cached?.revision === filingDiscoveryRevision) {
      return;
    }
    const requestRevision = filingDiscoveryRevision;
    const requestId = ++filingRequestIdRef.current;
    setFilingsLoading(true);
    setFilingsError(null);
    try {
      const data = await fetchSourceFilings(targetSymbol);
      if (filingRevisionRef.current !== requestRevision) return;
      setFilingsCache(prev => ({ ...prev, [targetSymbol]: { data, revision: requestRevision } }));
    } catch (err: any) {
      if (filingRevisionRef.current === requestRevision) {
        setFilingsError(err.message || `Failed to load source filings for ${targetSymbol}`);
      }
    } finally {
      if (filingRequestIdRef.current === requestId) setFilingsLoading(false);
    }
  }, [filingDiscoveryRevision, filingsCache]);

  // When user opens the 'filings' subtab, fetch on demand if not cached
  useEffect(() => {
    if (activeSubTab === 'filings') {
      loadSourceFilings(stock.symbol);
    }
  }, [activeSubTab, stock.symbol, loadSourceFilings]);

  const isAnalyzed = Boolean(
    docIntel && (
      (docIntel.promise_vs_delivery && docIntel.promise_vs_delivery.length > 0) ||
      (docIntel.what_changed_recently && docIntel.what_changed_recently.length > 0) ||
      (docIntel.growth_drivers && docIntel.growth_drivers.length > 0)
    )
  );

  const formattedTime = docIntel?.extraction_timestamp ? new Date(docIntel.extraction_timestamp).toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true
  }) : null;

  // Prefer the lifecycle count, then the current source response, then legacy stock links.
  const currentFilingsEntry = filingsCache[stock.symbol];
  const currentFilingsData = currentFilingsEntry?.revision === filingDiscoveryRevision ? currentFilingsEntry.data : null;
  const countDocuments = (response: SourceFilingsResponse) =>
    (response.documents?.annual_reports?.length || 0) +
    (response.documents?.concalls?.length || 0) +
    (response.documents?.presentations?.length || 0) +
    (response.documents?.material_announcements?.length || 0);
  const loadedFilingsCount = currentFilingsData ? countDocuments(currentFilingsData) : null;
  const fallbackStockLinksCount =
      (stock.documents?.annual_reports?.length || 0) +
      (stock.documents?.concalls?.length || 0) +
      (stock.documents?.presentations?.length || 0) +
      (stock.documents?.material_announcements?.length || 0);
  const totalFilingsCount = researchStatus?.filing_count ?? loadedFilingsCount ?? fallbackStockLinksCount;
  const hasTrustedFilingCount = Boolean(researchStatus && researchStatus.source_filings !== 'not_searched');
  const filingCollectionLabel = researchStatus?.source_filings === 'not_searched'
    ? 'source discovery has not run yet'
    : hasTrustedFilingCount
      ? `${totalFilingsCount} indexed source filings`
      : loadedFilingsCount !== null
        ? `${loadedFilingsCount} loaded source documents`
        : fallbackStockLinksCount > 0
          ? `${fallbackStockLinksCount} available source links`
          : 'available source links';
  const exploreFilingsLabel = researchStatus?.source_filings === 'not_searched'
    ? 'Explore Available Links'
    : `Explore ${totalFilingsCount} ${hasTrustedFilingCount ? 'Source Filings' : loadedFilingsCount !== null ? 'Source Documents' : 'Available Links'}`;

  return (
    <div className="space-y-8">
      
      {/* 1. Header & Provenance Banner */}
      <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-800 pb-5">
          <div className="flex items-start sm:items-center gap-3.5">
            <div className="w-11 h-11 rounded-2xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30 shrink-0">
              <Compass className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2.5 flex-wrap">
                <h3 className="text-xl font-bold text-white">
                  <ConceptHelp term="ai_interpretation" label="Business Analysis" />
                </h3>
                {isAnalyzed ? (
                  <>
                    <DataOriginBadge origin="ai_interpretation" />
                    <span className="bg-slate-900 text-slate-300 border border-slate-800 text-[11px] font-mono font-medium px-2.5 py-0.5 rounded-full">
                      Model: {docIntel?.model_version || docIntel?.ai_provider_used || 'GEMINI'}
                    </span>
                    {docIntel?.staleness_status === 'stale' && (
                      <span className="bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[11px] font-semibold px-2.5 py-0.5 rounded-full flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3 text-amber-400" />
                        Filings Updated (Analysis Stale)
                      </span>
                    )}
                    {formattedTime && (
                      <span className="bg-slate-900 text-slate-300 border border-slate-800 text-[11px] font-mono font-medium px-2.5 py-0.5 rounded-full flex items-center gap-1.5">
                        <Clock className="w-3 h-3 text-cyan-400" />
                        Last Analyzed: {formattedTime}
                      </span>
                    )}
                  </>
                ) : (
                  <span className="bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[11px] font-semibold px-2.5 py-0.5 rounded-full flex items-center gap-1">
                    <HelpCircle className="w-3 h-3" />
                    Analysis Not Run Yet
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Fundamental investor thesis, business monetization model, management execution track record, and source-linked filings
              </p>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2.5 flex-wrap">
            <button
              onClick={onOpenKeyModal}
              className="bg-slate-900 hover:bg-slate-800 text-slate-300 font-bold text-xs px-3.5 py-2 rounded-xl border border-slate-700 flex items-center gap-1.5 transition-all"
            >
              <KeyRound className="w-3.5 h-3.5 text-amber-400" />
              <span>{aiStatus?.configured && aiStatus.status === 'active' ? 'Gemini Key Active ✓' : 'Configure Gemini Key'}</span>
            </button>

            <button
              onClick={onGenerateIntel}
              disabled={generatingDocIntel}
              className="bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-500 text-slate-950 font-bold text-xs px-3.5 py-2 rounded-xl flex items-center gap-1.5 transition-all shadow-sm shadow-emerald-600/20"
            >
              <Zap className={`w-3.5 h-3.5 ${generatingDocIntel ? 'animate-spin' : ''}`} />
              <span>{generatingDocIntel ? 'Extracting with AI...' : (isAnalyzed ? 'Re-run Fresh Analysis' : 'Run Live AI Analysis')}</span>
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

        {/* Invitation Hero when unanalyzed */}
        {!isAnalyzed && (
          <div className="bg-slate-950/90 border border-slate-800 p-8 rounded-3xl text-center space-y-5 bg-gradient-to-b from-slate-950 to-slate-900/60">
            <div className="w-14 h-14 rounded-3xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20 mx-auto">
              <Sparkles className="w-7 h-7" />
            </div>
            <div className="space-y-2 max-w-lg mx-auto">
              <h4 className="text-lg font-bold text-white">Deep AI Fundamental Analysis Not Run Yet</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                Stocker can scan and triangulate <strong className="text-emerald-300">{filingCollectionLabel}</strong> (Annual Reports, Concall Transcripts, Investor PPTs) against <strong className="text-cyan-300">historical standardized financial statements</strong> to assess management guidance, capex roadmaps, and balance sheet cash flows.
              </p>
            </div>
            
            <div className="flex items-center justify-center gap-3 pt-2 flex-wrap">
              <button
                onClick={onGenerateIntel}
                disabled={generatingDocIntel}
                className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs px-6 py-3 rounded-2xl flex items-center gap-2 transition-all shadow-lg shadow-emerald-500/20 disabled:bg-slate-800 disabled:text-slate-500"
              >
                <Zap className={`w-4 h-4 ${generatingDocIntel ? 'animate-spin' : ''}`} />
                <span>{generatingDocIntel ? 'Executing Live Extraction...' : 'Run Live AI Analysis Now'}</span>
              </button>
              <button
                onClick={() => setActiveSubTab('filings')}
                className="bg-slate-900 hover:bg-slate-800 text-slate-300 font-bold text-xs px-4 py-3 rounded-2xl border border-slate-800 flex items-center gap-1.5"
              >
                <FileText className="w-4 h-4 text-emerald-400" />
                <span>{exploreFilingsLabel}</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 2. Unified 4-Tab Navigation Bar */}
      <div className="flex items-center gap-1.5 p-1 bg-slate-950 rounded-2xl border border-slate-800 overflow-x-auto">
        <button
          onClick={() => setActiveSubTab('investment')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 whitespace-nowrap ${
            activeSubTab === 'investment'
              ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>1. Investment View</span>
        </button>

        <button
          onClick={() => setActiveSubTab('growth')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 whitespace-nowrap ${
            activeSubTab === 'growth'
              ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <TrendingUp className="w-3.5 h-3.5" />
          <span>2. Business & Growth</span>
        </button>

        <button
          onClick={() => setActiveSubTab('management')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 whitespace-nowrap ${
            activeSubTab === 'management'
              ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span>3. Management & Execution</span>
        </button>

        <button
          onClick={() => setActiveSubTab('filings')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 whitespace-nowrap ${
            activeSubTab === 'filings'
              ? 'bg-indigo-500 text-slate-950 shadow-md shadow-indigo-500/20'
              : 'text-slate-400 hover:text-white hover:bg-slate-900'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>4. Source Filings</span>
          <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${
            activeSubTab === 'filings' ? 'bg-slate-950/20 text-slate-950' : 'bg-slate-900 text-slate-400'
          }`}>
            {filingDiscoveryState === 'running'
              ? '…'
              : researchStatus?.source_filings === 'not_searched'
                ? 'Not searched'
                : totalFilingsCount}
          </span>
        </button>
      </div>

      {/* 3. Render Active Subtab */}
      {activeSubTab !== 'filings' && loadingDocIntel && (
        <div className="glass-panel rounded-3xl p-10 border border-slate-800 text-center space-y-3">
          <RefreshCw className="w-5 h-5 text-cyan-400 animate-spin mx-auto" />
          <p className="text-xs text-slate-400">Checking for existing Business Analysis…</p>
        </div>
      )}

      {activeSubTab !== 'filings' && !loadingDocIntel && !isAnalyzed && (
        <div className="glass-panel rounded-3xl p-8 border border-slate-800 text-center space-y-4">
          <Sparkles className="w-7 h-7 text-slate-500 mx-auto" />
          <div className="space-y-2 max-w-xl mx-auto">
            <h4 className="text-base font-bold text-white">Business analysis has not been run yet.</h4>
            <p className="text-xs text-slate-400 leading-relaxed">Run Analysis to extract management guidance, growth drivers, competitive position, risks and execution history from company filings.</p>
          </div>
          <button onClick={onGenerateIntel} disabled={generatingDocIntel} className="bg-emerald-500 hover:bg-emerald-400 disabled:bg-slate-800 disabled:text-slate-500 text-slate-950 font-bold text-xs px-5 py-2.5 rounded-xl inline-flex items-center gap-2">
            <Zap className={`w-4 h-4 ${generatingDocIntel ? 'animate-spin' : ''}`} />
            <span>{generatingDocIntel ? 'Running Analysis…' : 'Run Analysis'}</span>
          </button>
        </div>
      )}

      {isAnalyzed && docIntel && (
        <>
          {activeSubTab === 'investment' && (
            <InvestmentView docIntel={docIntel} companyName={stock.name} />
          )}

          {activeSubTab === 'growth' && (
            <BusinessGrowthView docIntel={docIntel} companyName={stock.name} />
          )}

          {activeSubTab === 'management' && (
            <ManagementExecutionView docIntel={docIntel} companyName={stock.name} />
          )}

        </>
      )}

      {activeSubTab === 'filings' && (
        <SourceFilingsView
          symbol={stock.symbol}
          companyName={stock.name}
          filingsData={currentFilingsData}
          loading={filingsLoading}
          error={filingsError}
          onRetry={() => loadSourceFilings(stock.symbol, true)}
        />
      )}

    </div>
  );
};
