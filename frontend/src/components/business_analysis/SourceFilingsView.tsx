import React, { useState, useMemo } from 'react';
import { DocumentLinks, DocumentItem, DocumentSummaryItem, SourceFilingsResponse } from '../../types';
import { 
  FileText, ExternalLink, Search, Sparkles, 
  Mic, Presentation, Bell, ChevronDown, CheckCircle2, AlertTriangle, RefreshCw,
  Globe, ShieldCheck, FileCheck
} from 'lucide-react';
import { 
  sortDocumentsGlobally, 
  formatDocumentDisplayType, 
  formatDocumentSources 
} from '../../utils/documentChronology';

interface SourceFilingsViewProps {
  symbol: string;
  companyName: string;
  filingsData: SourceFilingsResponse | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

export const SourceFilingsView: React.FC<SourceFilingsViewProps> = ({
  symbol,
  companyName,
  filingsData,
  loading,
  error,
  onRetry
}) => {
  const [filterType, setFilterType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedDocKeys, setExpandedDocKeys] = useState<Set<string>>(new Set());

  const documents = filingsData?.documents;
  const summariesMap = filingsData?.summaries || {};

  // 1. Compile all source documents with backend/canonical deduplication
  const allDocs = useMemo<DocumentItem[]>(() => {
    if (!documents) return [];
    
    // If backend provided pre-sorted all_documents, use it
    if (documents.all_documents && documents.all_documents.length > 0) {
      return sortDocumentsGlobally(documents.all_documents);
    }
    
    // Otherwise gather from all typed category lists
    const rawList: DocumentItem[] = [];
    if (documents.annual_reports) rawList.push(...documents.annual_reports);
    if (documents.regulatory_annual_filings) rawList.push(...documents.regulatory_annual_filings);
    if (documents.concalls) rawList.push(...documents.concalls);
    if (documents.presentations) rawList.push(...documents.presentations);
    if (documents.material_announcements) rawList.push(...documents.material_announcements);
    if (documents.brsr_reports) rawList.push(...documents.brsr_reports);
    if (documents.other_filings) rawList.push(...documents.other_filings);
    
    // Deduplicate by doc_key or clean canonical URL
    const seen = new Map<string, DocumentItem>();
    for (const d of rawList) {
      const key = d.doc_key || (d.url ? d.url.split('#')[0].trim() : '') || d.title;
      if (!seen.has(key)) {
        seen.set(key, d);
      }
    }
    return sortDocumentsGlobally(Array.from(seen.values()));
  }, [documents]);

  const toggleExpandDoc = (docKeyOrUrl: string) => {
    setExpandedDocKeys(prev => {
      const next = new Set(prev);
      if (next.has(docKeyOrUrl)) {
        next.delete(docKeyOrUrl);
      } else {
        next.add(docKeyOrUrl);
      }
      return next;
    });
  };

  // Category counts
  const categoryCounts = useMemo(() => {
    const counts = {
      all: allDocs.length,
      annual_report: 0,
      regulatory_annual_filing: 0,
      concall: 0,
      presentation: 0,
      announcement: 0,
      brsr_esg: 0
    };
    for (const d of allDocs) {
      const dt = (d.doc_type || '').toLowerCase();
      if (dt === 'regulatory_annual_filing' || dt.includes('20-f')) {
        counts.regulatory_annual_filing++;
      } else if (dt === 'brsr_esg' || dt.includes('brsr') || dt.includes('esg')) {
        counts.brsr_esg++;
      } else if (dt === 'annual_report' || dt.includes('annual')) {
        counts.annual_report++;
      } else if (dt === 'concall_transcript' || dt.includes('concall')) {
        counts.concall++;
      } else if (dt === 'presentation' || dt.includes('presentation')) {
        counts.presentation++;
      } else if (dt === 'announcement' || dt.includes('announcement')) {
        counts.announcement++;
      }
    }
    return counts;
  }, [allDocs]);

  // Filter and search
  const filteredDocs = useMemo(() => {
    return allDocs.filter(d => {
      const dt = (d.doc_type || '').toLowerCase();
      const matchesType = 
        filterType === 'all' ? true :
        filterType === 'annual_report' ? (dt === 'annual_report' && !dt.includes('brsr') && !dt.includes('20-f')) :
        filterType === 'regulatory_annual_filing' ? (dt === 'regulatory_annual_filing' || dt.includes('20-f')) :
        filterType === 'concall' ? (dt === 'concall_transcript' || dt.includes('concall')) :
        filterType === 'presentation' ? (dt === 'presentation' || dt.includes('presentation')) :
        filterType === 'announcement' ? (dt === 'announcement' || dt.includes('announcement')) :
        filterType === 'brsr_esg' ? (dt === 'brsr_esg' || dt.includes('brsr') || dt.includes('esg')) : true;

      const q = searchQuery.toLowerCase().trim();
      const matchesSearch = q === '' ? true :
        (d.title || '').toLowerCase().includes(q) ||
        (d.period_or_date || '').toLowerCase().includes(q) ||
        (d.discovery_source || '').toLowerCase().includes(q) ||
        (d.doc_type || '').toLowerCase().includes(q) ||
        (d.discovered_sources && d.discovered_sources.some(s => s.toLowerCase().includes(q)));

      return matchesType && matchesSearch;
    });
  }, [allDocs, filterType, searchQuery]);

  const getDocTypeIcon = (docType?: string) => {
    if (!docType) return <FileText className="w-4 h-4 text-cyan-400" />;
    const t = docType.toLowerCase();
    if (t === 'regulatory_annual_filing' || t.includes('20-f')) return <FileCheck className="w-4 h-4 text-indigo-400" />;
    if (t === 'brsr_esg' || t.includes('brsr') || t.includes('esg')) return <ShieldCheck className="w-4 h-4 text-teal-400" />;
    if (t === 'annual_report' || t.includes('annual')) return <FileText className="w-4 h-4 text-cyan-400" />;
    if (t.includes('concall')) return <Mic className="w-4 h-4 text-amber-400" />;
    if (t.includes('presentation')) return <Presentation className="w-4 h-4 text-emerald-400" />;
    if (t.includes('announcement')) return <Bell className="w-4 h-4 text-rose-400" />;
    return <FileText className="w-4 h-4 text-cyan-400" />;
  };

  return (
    <div className="space-y-6">

      {/* Header & Filter Controls */}
      <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-cyan-500/20 text-cyan-400 flex items-center justify-center border border-cyan-500/30 shrink-0">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-base font-bold text-white flex items-center gap-2">
                <span>Unified Sourced Filings & AI Findings</span>
                {!loading && (
                  <span className="bg-slate-900 text-cyan-400 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-slate-800">
                    {allDocs.length} unique canonical filings
                  </span>
                )}
              </h4>
              <p className="text-xs text-slate-400">Chronological timeline of annual reports, 20-F filings, concalls, presentations, announcements and ESG reports</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onRetry}
              disabled={loading}
              className="bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-slate-300 text-xs px-3 py-2 rounded-xl flex items-center gap-1.5 border border-slate-700 transition-all shrink-0"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh list</span>
            </button>
            <div className="relative min-w-[220px]">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search filings by title or period..."
                className="w-full bg-slate-950 text-xs text-slate-200 pl-8 pr-3 py-2 rounded-xl border border-slate-800 focus:outline-none focus:border-cyan-500/50"
              />
            </div>
          </div>
        </div>

        {/* Filter Buttons */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          {[
            { id: 'all', label: 'All Documents', count: categoryCounts.all },
            { id: 'annual_report', label: 'Annual Reports', count: categoryCounts.annual_report },
            { id: 'regulatory_annual_filing', label: 'Regulatory (20-F)', count: categoryCounts.regulatory_annual_filing },
            { id: 'concall', label: 'Concalls', count: categoryCounts.concall },
            { id: 'presentation', label: 'Presentations', count: categoryCounts.presentation },
            { id: 'announcement', label: 'Material Announcements', count: categoryCounts.announcement },
            { id: 'brsr_esg', label: 'BRSR / ESG', count: categoryCounts.brsr_esg },
          ].map(btn => (
            <button
              key={btn.id}
              onClick={() => setFilterType(btn.id)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all flex items-center gap-1.5 ${
                filterType === btn.id
                  ? 'bg-cyan-500 text-slate-950 shadow-sm shadow-cyan-500/20'
                  : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
              }`}
            >
              <span>{btn.label}</span>
              <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${filterType === btn.id ? 'bg-slate-950/20 text-slate-950' : 'bg-slate-900 text-slate-400'}`}>
                {btn.count}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="glass-panel rounded-3xl p-12 border border-slate-800 text-center space-y-3">
          <div className="w-8 h-8 border-2 border-cyan-500/30 border-t-cyan-400 rounded-full animate-spin mx-auto" />
          <p className="text-xs text-slate-300 font-medium">Loading source filings and document summaries for {companyName}...</p>
        </div>
      )}

      {/* Error State */}
      {!loading && error && (
        <div className="bg-rose-950/30 border border-rose-800/50 p-6 rounded-2xl flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3 text-rose-300 text-xs">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={onRetry}
            className="bg-rose-900/60 hover:bg-rose-800 text-rose-200 text-xs px-3.5 py-1.5 rounded-xl flex items-center gap-1.5 border border-rose-700/50 transition-all shrink-0"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry Loading</span>
          </button>
        </div>
      )}

      {/* Filings List */}
      {!loading && !error && (
        <div className="space-y-4">
          {filteredDocs.length > 0 ? (
            filteredDocs.map((doc, idx) => {
              const getSummaryForDoc = (): DocumentSummaryItem | undefined => {
                if (doc.doc_key && summariesMap[doc.doc_key]) {
                  return summariesMap[doc.doc_key];
                }
                if (doc.url && summariesMap[doc.url]) {
                  return summariesMap[doc.url];
                }
                const cleanUrl = doc.url ? doc.url.split('#')[0].trim() : '';
                if (cleanUrl && summariesMap[cleanUrl]) {
                  return summariesMap[cleanUrl];
                }
                return undefined;
              };

              const summary = getSummaryForDoc();
              const isFailed = (summary && summary.status === 'failed') || doc.ai_status === 'PROCESSING_FAILED';
              const isAnalyzed = Boolean(!isFailed && summary && ((summary.key_takeaways && summary.key_takeaways.length > 0) || (summary.extracted_facts && summary.extracted_facts.length > 0)));
              const isNotSelected = Boolean(!isAnalyzed && !isFailed && (doc.ai_status === 'NOT_SELECTED' || (filingsData?.has_company_analysis && !summary)));
              const docKeyOrUrl = doc.doc_key || doc.url || `doc_${idx}`;
              const isExpanded = expandedDocKeys.has(docKeyOrUrl);
              const displayType = formatDocumentDisplayType(doc.doc_type);
              const sourcesText = formatDocumentSources(doc);

              return (
                <div key={docKeyOrUrl} className="glass-panel rounded-2xl p-5 md:p-6 border border-slate-800/90 space-y-4 hover:border-slate-700 transition-all bg-slate-950/80">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-start sm:items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center shrink-0">
                        {getDocTypeIcon(doc.doc_type)}
                      </div>
                      <div>
                        <h5 className="text-sm font-bold text-white flex items-center gap-2 flex-wrap">
                          <span>{doc.title}</span>
                          <span className="bg-slate-900 text-cyan-300 text-[10px] font-semibold px-2 py-0.5 rounded-full border border-slate-800">
                            {displayType}
                          </span>
                          {isAnalyzed && (
                            <span className="bg-emerald-500/10 text-emerald-400 text-[10px] font-semibold px-2 py-0.5 rounded-full border border-emerald-500/20 flex items-center gap-1">
                              <Sparkles className="w-2.5 h-2.5" />
                              AI Analyzed
                            </span>
                          )}
                          {isFailed && (
                            <span className="bg-rose-500/10 text-rose-400 text-[10px] font-semibold px-2 py-0.5 rounded-full border border-rose-500/20 flex items-center gap-1">
                              <AlertTriangle className="w-2.5 h-2.5" />
                              AI Extraction Failed
                            </span>
                          )}
                          {isNotSelected && (
                            <span className="bg-slate-900 text-slate-400 text-[10px] font-mono px-2 py-0.5 rounded-full border border-slate-800">
                              Not in working set
                            </span>
                          )}
                          {summary?.management_tone && (
                            <span className="bg-slate-900 text-slate-300 text-[10px] font-mono px-2 py-0.5 rounded-full border border-slate-800">
                              Tone: {summary.management_tone}
                            </span>
                          )}
                        </h5>
                        <p className="text-xs text-slate-400 font-mono mt-0.5 flex items-center gap-1.5 flex-wrap">
                          <span>{doc.period_or_date || 'Undated'}</span>
                          <span>•</span>
                          <span>{sourcesText}</span>
                          {doc.source_aliases && doc.source_aliases.length > 0 && (
                            <span className="text-[10px] text-slate-500 italic">
                              (also referenced as: {doc.source_aliases.join(', ')})
                            </span>
                          )}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-end sm:self-center">
                      {isAnalyzed && (
                        <button
                          onClick={() => toggleExpandDoc(docKeyOrUrl)}
                          className="text-xs text-cyan-400 hover:text-cyan-300 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/20 px-3 py-1.5 rounded-xl font-medium flex items-center gap-1 transition-all"
                        >
                          <span>{isExpanded ? 'Hide AI Details' : 'View AI Findings'}</span>
                          <ChevronDown className={`w-3.5 h-3.5 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                        </button>
                      )}

                      {doc.url && (
                        <a
                          href={doc.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-slate-300 hover:text-white bg-slate-900 hover:bg-slate-800 border border-slate-700 px-3 py-1.5 rounded-xl font-medium flex items-center gap-1.5 transition-all"
                        >
                          <span>Open Filing</span>
                          <ExternalLink className="w-3 h-3 text-cyan-400" />
                        </a>
                      )}
                    </div>
                  </div>

                  {isFailed && (
                    <p className="text-[11px] text-rose-400/90 border-t border-slate-900 pt-3 flex items-center gap-1.5">
                      <AlertTriangle className="w-3 h-3 text-rose-400 shrink-0" />
                      {summary?.error || doc.ai_failure_reason || 'AI extraction attempted but document processing could not be completed.'}
                    </p>
                  )}

                  {isNotSelected && (
                    <p className="text-[11px] text-slate-400 border-t border-slate-900 pt-3 flex items-center gap-1.5">
                      <FileText className="w-3 h-3 text-slate-500 shrink-0" />
                      Not included in the current AI working set.
                    </p>
                  )}

                  {!isAnalyzed && !isFailed && !isNotSelected && (
                    <p className="text-[11px] text-slate-400 border-t border-slate-900 pt-3 flex items-center gap-1.5">
                      <Sparkles className="w-3 h-3 text-slate-500 shrink-0" />
                      Run Analysis to see AI findings for this filing.
                    </p>
                  )}

                  {/* Expanded AI Findings Section (Supports multiple expanded cards simultaneously) */}
                  {isExpanded && isAnalyzed && summary && (
                    <div className="mt-4 pt-4 border-t border-slate-900 space-y-4 bg-slate-950 p-4 rounded-xl border border-slate-800/80">
                      
                      {/* Key Takeaways */}
                      {summary.key_takeaways && summary.key_takeaways.length > 0 && (
                        <div className="space-y-2">
                          <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-wider block">
                            Executive Takeaways:
                          </span>
                          <ul className="space-y-1.5 text-xs text-slate-300">
                            {summary.key_takeaways.map((t: string, tIdx: number) => (
                              <li key={tIdx} className="flex items-start gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0 mt-1.5" />
                                <span>{t}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Forward Guidance & Capex */}
                      {summary.guidance_and_capex && (
                        <div className="text-xs text-slate-300 bg-slate-900/60 p-3 rounded-xl border border-slate-800/40">
                          <strong className="text-cyan-400 block mb-1">Guidance & Capex Outlook:</strong>
                          <p>{summary.guidance_and_capex}</p>
                        </div>
                      )}

                      {/* Extracted Structured Facts */}
                      {summary.extracted_facts && summary.extracted_facts.length > 0 && (
                        <div className="space-y-2">
                          <span className="text-[11px] font-bold text-amber-400 uppercase tracking-wider block">
                            Extracted Structured Facts ({summary.extracted_facts.length}):
                          </span>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                            {summary.extracted_facts.map((f: any, fIdx: number) => (
                              <div key={fIdx} className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800 text-xs space-y-1">
                                <div className="flex items-center justify-between">
                                  <span className="font-semibold text-slate-200">{f.metric_name}</span>
                                  <span className="font-mono text-cyan-400 font-bold">{f.stated_value_raw}</span>
                                </div>
                                {f.source_quote && (
                                  <p className="text-[10px] text-slate-400 italic line-clamp-2">"{f.source_quote}"</p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className="glass-panel rounded-3xl p-8 border border-slate-800 text-center text-xs text-slate-400">
              No source documents match your current filter.
            </div>
          )}
        </div>
      )}

    </div>
  );
};
