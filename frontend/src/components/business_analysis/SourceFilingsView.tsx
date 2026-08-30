import React, { useState } from 'react';
import { BusinessAnalysisIntelligence, DocumentLinks, DocumentItem } from '../../types';
import { 
  FileText, ExternalLink, Search, Sparkles, 
  Mic, Presentation, Bell, Layers, ChevronDown, ChevronRight, CheckCircle2, AlertTriangle
} from 'lucide-react';
import { DataOriginBadge } from '../ui/DataOriginBadge';

interface SourceFilingsViewProps {
  docIntel: BusinessAnalysisIntelligence;
  documents?: DocumentLinks;
  companyName: string;
}

export const SourceFilingsView: React.FC<SourceFilingsViewProps> = ({ docIntel, documents, companyName }) => {
  const [filterType, setFilterType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedDocUrl, setExpandedDocUrl] = useState<string | null>(null);

  // Compile all verified filings
  const allDocs: DocumentItem[] = [];
  if (documents?.annual_reports) allDocs.push(...documents.annual_reports);
  if (documents?.concalls) allDocs.push(...documents.concalls);
  if (documents?.investor_presentations) allDocs.push(...documents.investor_presentations);
  if (documents?.announcements) allDocs.push(...documents.announcements);

  const summariesMap = new Map<string, any>();
  if (docIntel.document_summaries) {
    for (const s of docIntel.document_summaries) {
      if (s.doc_url) summariesMap.set(s.doc_url, s);
    }
  }

  // Filter docs
  const filteredDocs = allDocs.filter(d => {
    const matchesType = 
      filterType === 'all' ? true :
      filterType === 'annual_report' ? (d.doc_type === 'annual_report' || d.type?.includes('Annual')) :
      filterType === 'concall' ? (d.doc_type === 'concall_transcript' || d.type?.includes('Concall')) :
      filterType === 'presentation' ? (d.doc_type === 'presentation' || d.type?.includes('Presentation')) :
      filterType === 'announcement' ? (d.doc_type === 'announcement' || d.type?.includes('Announcement')) : true;

    const matchesSearch = searchQuery.trim() === '' ? true :
      (d.title || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (d.period_or_date || '').toLowerCase().includes(searchQuery.toLowerCase());

    return matchesType && matchesSearch;
  });

  const getDocTypeIcon = (type?: string) => {
    if (!type) return <FileText className="w-4 h-4 text-cyan-400" />;
    const t = type.toLowerCase();
    if (t.includes('annual')) return <FileText className="w-4 h-4 text-cyan-400" />;
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
                <span className="bg-slate-900 text-cyan-400 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-slate-800">
                  {allDocs.length} verified documents
                </span>
              </h4>
              <p className="text-xs text-slate-400">Official Annual Reports, Concall Transcripts, Investor PPTs & Announcements with AI insights</p>
            </div>
          </div>

          {/* Search Input */}
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

        {/* Filter Buttons */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          {[
            { id: 'all', label: 'All Documents', count: allDocs.length },
            { id: 'annual_report', label: 'Annual Reports', count: documents?.annual_reports?.length || 0 },
            { id: 'concall', label: 'Concalls', count: documents?.concalls?.length || 0 },
            { id: 'presentation', label: 'Presentations', count: documents?.investor_presentations?.length || 0 },
            { id: 'announcement', label: 'Announcements', count: documents?.announcements?.length || 0 },
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

      {/* Filings List */}
      <div className="space-y-4">
        {filteredDocs.length > 0 ? (
          filteredDocs.map((doc, idx) => {
            const summary = summariesMap.get(doc.url);
            const isExpanded = expandedDocUrl === doc.url;
            const hasAiAnalysis = Boolean(summary && (summary.key_takeaways?.length > 0 || summary.extracted_facts?.length > 0));

            return (
              <div key={idx} className="glass-panel rounded-2xl p-5 md:p-6 border border-slate-800/90 space-y-4 hover:border-slate-700 transition-all bg-slate-950/80">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-start sm:items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center shrink-0">
                      {getDocTypeIcon(doc.doc_type || doc.type)}
                    </div>
                    <div>
                      <h5 className="text-sm font-bold text-white flex items-center gap-2 flex-wrap">
                        <span>{doc.title}</span>
                        {hasAiAnalysis && (
                          <span className="bg-emerald-500/10 text-emerald-400 text-[10px] font-semibold px-2 py-0.5 rounded-full border border-emerald-500/20 flex items-center gap-1">
                            <Sparkles className="w-2.5 h-2.5" />
                            AI Analyzed
                          </span>
                        )}
                        {summary?.management_tone && (
                          <span className="bg-slate-900 text-slate-300 text-[10px] font-mono px-2 py-0.5 rounded-full border border-slate-800">
                            Tone: {summary.management_tone}
                          </span>
                        )}
                      </h5>
                      <p className="text-xs text-slate-400 font-mono mt-0.5">
                        {doc.period_or_date || doc.period || 'Official Filing'} • {doc.discovery_source || 'Exchange Sourced'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-center">
                    {hasAiAnalysis && (
                      <button
                        onClick={() => setExpandedDocUrl(isExpanded ? null : doc.url)}
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

                {/* Expanded AI Findings Section */}
                {isExpanded && summary && (
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

    </div>
  );
};
