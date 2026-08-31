import React from 'react';
import { BusinessAnalysisIntelligence } from '../../types';
import { 
  CheckCircle2, AlertTriangle, Clock, Target, 
  ExternalLink, ShieldCheck, Calculator, Activity, HelpCircle, Layers
} from 'lucide-react';
import { DataOriginBadge } from '../ui/DataOriginBadge';

interface ManagementExecutionViewProps {
  docIntel: BusinessAnalysisIntelligence;
  companyName: string;
}

export const ManagementExecutionView: React.FC<ManagementExecutionViewProps> = ({ docIntel, companyName }) => {
  const promiseVsDelivery = docIntel.promise_vs_delivery || [];
  const managementGuidance = docIntel.management_guidance_items || [];
  const guidanceVsProj = docIntel.guidance_vs_projections || [];
  const verifiedFacts = docIntel.verified_facts || [];
  const capitalAlloc = docIntel.capital_allocation;
  const governanceWatch = docIntel.governance_watch;

  return (
    <div className="space-y-8">

      {/* 1. Promise vs Delivery Track Record */}
      <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30 shrink-0">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-base font-bold text-white flex items-center gap-2">
                <span>Management Promise vs Delivery Track Record</span>
                <span className="bg-slate-900 text-emerald-400 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-slate-800">
                  {promiseVsDelivery.length} documented commitments
                </span>
              </h4>
              <p className="text-xs text-slate-400">Comparing past guidance statements directly against subsequently reported outcomes</p>
            </div>
          </div>
        </div>

        {promiseVsDelivery.length > 0 ? (
          <div className="space-y-4">
            {promiseVsDelivery.map((item, idx) => {
              const statusBg = 
                item.status === 'Delivered' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' :
                item.status === 'In Progress' ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30' :
                item.status === 'Delayed' ? 'bg-amber-500/10 text-amber-400 border-amber-500/30' :
                item.status === 'Missed' ? 'bg-rose-500/10 text-rose-400 border-rose-500/30' :
                'bg-slate-800 text-slate-400 border-slate-700';

              return (
                <div key={idx} className="bg-slate-950 p-5 md:p-6 rounded-2xl border border-slate-800 space-y-4 hover:border-slate-700 transition-all">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-900 pb-3">
                    <div className="flex items-center gap-2.5">
                      <span className="text-sm font-bold text-white">{item.area}</span>
                      <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border ${statusBg}`}>
                        {item.status}
                      </span>
                    </div>
                  </div>

                  {/* 2-Column Comparison: Promise vs Outcome */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    
                    {/* Management Promised */}
                    <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800/60 space-y-2">
                      <div className="flex items-center justify-between text-[11px] text-slate-400">
                        <span className="font-semibold text-slate-300">Management Guided:</span>
                        <span className="font-mono text-cyan-400">{item.promised_in_period}</span>
                      </div>
                      <p className="text-xs text-slate-200 leading-relaxed font-medium">"{item.management_promise}"</p>
                      {item.source_url_promise && (
                        <a
                          href={item.source_url_promise}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[10px] text-slate-500 hover:text-cyan-400 flex items-center gap-1 transition-colors pt-1"
                        >
                          <span>Promise Filing</span>
                          {item.promise_source_page && <span className="font-mono text-cyan-400">p.{item.promise_source_page}</span>}
                          <ExternalLink className="w-2.5 h-2.5" />
                        </a>
                      )}
                    </div>

                    {/* Actual Outcome Reported */}
                    <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800/60 space-y-2">
                      <div className="flex items-center justify-between text-[11px] text-slate-400">
                        <span className="font-semibold text-slate-300">Actual Outcome:</span>
                        <span className="font-mono text-emerald-400">{item.actual_in_period}</span>
                      </div>
                      <p className="text-xs text-slate-200 leading-relaxed font-medium">"{item.actual_outcome}"</p>
                      {item.source_url_actual && (
                        <a
                          href={item.source_url_actual}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[10px] text-slate-500 hover:text-emerald-400 flex items-center gap-1 transition-colors pt-1"
                        >
                          <span>Outcome Filing</span>
                          {item.actual_source_page && <span className="font-mono text-emerald-400">p.{item.actual_source_page}</span>}
                          <ExternalLink className="w-2.5 h-2.5" />
                        </a>
                      )}
                    </div>

                  </div>

                  {/* Stocker Analysis & Numbers Verification */}
                  {item.stocker_analysis && (
                    <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/40 p-3 rounded-xl border border-slate-800/40">
                      <strong className="text-cyan-400">Variance Analysis:</strong> {item.stocker_analysis}
                    </p>
                  )}

                  {item.financial_numbers_check && (
                    <div className="text-[11px] text-cyan-300 font-mono bg-cyan-950/20 p-2.5 rounded-xl border border-cyan-800/30 flex items-center gap-2">
                      <Calculator className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                      <span>{item.financial_numbers_check}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="bg-slate-950/60 p-6 rounded-2xl border border-slate-800 text-center text-xs text-slate-400">
            No documented promise vs delivery items compiled yet.
          </div>
        )}
      </div>

      {/* 1B. Structured Management Guidance & Verified Actuals */}
      {managementGuidance.length > 0 && (
        <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-cyan-500/20 text-cyan-400 flex items-center justify-center border border-cyan-500/30 shrink-0">
                <Target className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-base font-bold text-white flex items-center gap-2">
                  <span>Structured Management Guidance & Verification</span>
                  <span className="bg-slate-900 text-cyan-400 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-slate-800">
                    {managementGuidance.length} tracked items
                  </span>
                </h4>
                <p className="text-xs text-slate-400">Deterministic code comparison against audited financial statements and verified milestones</p>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            {managementGuidance.map((g, idx) => {
              const statusBg =
                g.status === 'MET' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' :
                g.status === 'PARTIALLY_MET' ? 'bg-amber-500/10 text-amber-400 border-amber-500/30' :
                g.status === 'MISSED' ? 'bg-rose-500/10 text-rose-400 border-rose-500/30' :
                g.status === 'NOT_YET_DUE' ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30' :
                'bg-slate-800 text-slate-400 border-slate-700';

              return (
                <div key={idx} className="bg-slate-950 p-5 rounded-2xl border border-slate-800 space-y-3 hover:border-slate-700 transition-all">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-900 pb-3">
                    <div className="flex items-center gap-2.5">
                      <span className="text-sm font-bold text-white">{g.metric_or_topic}</span>
                      <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border ${statusBg}`}>
                        {g.status}
                      </span>
                    </div>
                    <span className="text-xs text-slate-400 font-mono">Target: {g.target_period}</span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/40 space-y-1.5">
                      <div className="text-[11px] text-slate-400 font-semibold">Management Guidance:</div>
                      <p className="text-xs text-slate-200 font-medium">"{g.guidance_text}"</p>
                      {g.source_document_title && (
                        <div className="text-[10px] text-slate-500 flex items-center gap-1 pt-1">
                          <span>Source: {g.source_document_title}</span>
                          {g.source_document_url && (
                            <a href={g.source_document_url} target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline inline-flex items-center gap-0.5">
                              <ExternalLink className="w-2.5 h-2.5" />
                            </a>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/40 space-y-1.5">
                      <div className="text-[11px] text-slate-400 font-semibold">Reported Actual / Evaluation:</div>
                      {g.actual_reported_value !== null && g.actual_reported_value !== undefined ? (
                        <div className="text-sm font-mono font-bold text-emerald-400">
                          {g.actual_reported_value} {g.unit || ''} ({g.actual_reported_period || g.target_period})
                        </div>
                      ) : (
                        <div className="text-xs font-mono text-slate-400 italic">No exact quantitative line-item reported</div>
                      )}
                      {g.comparison_detail && (
                        <p className="text-xs text-slate-300 pt-1">{g.comparison_detail}</p>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 2. Management Guidance vs Stocker DCF Projections */}
      <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-cyan-500/20 text-cyan-400 flex items-center justify-center border border-cyan-500/30 shrink-0">
              <Calculator className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-base font-bold text-white flex items-center gap-2">
                <span>Management Guidance vs Stocker DCF Projections</span>
                <span className="bg-slate-900 text-cyan-400 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-slate-800">
                  {guidanceVsProj.length} comparisons
                </span>
              </h4>
              <p className="text-xs text-slate-400">Triangulating corporate targets against Stocker's independent DCF assumptions and current run-rate</p>
            </div>
          </div>
        </div>

        {guidanceVsProj.length > 0 ? (
          <div className="space-y-4">
            {guidanceVsProj.map((item, idx) => (
              <div key={idx} className="bg-slate-950 p-5 rounded-2xl border border-slate-800 space-y-3 hover:border-slate-700 transition-all">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-900 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-white">{item.metric_name}</span>
                    <span className="text-xs text-slate-400 font-mono">Target: {item.period_target}</span>
                  </div>
                  {item.variance_guidance_vs_base_bps !== undefined && item.variance_guidance_vs_base_bps !== null && (
                    <span className={`text-xs font-mono font-bold px-2.5 py-0.5 rounded-full border ${
                      item.variance_guidance_vs_base_bps >= 0 ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                    }`}>
                      {item.variance_guidance_vs_base_bps >= 0 ? `+${item.variance_guidance_vs_base_bps} bps vs Stocker Base` : `${item.variance_guidance_vs_base_bps} bps vs Stocker Base`}
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                  <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800/40">
                    <span className="text-slate-400 block mb-1">Management Guidance:</span>
                    <span className="text-white font-mono font-bold text-sm">{item.management_guidance_raw}</span>
                  </div>
                  <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800/40">
                    <span className="text-slate-400 block mb-1">Stocker Base DCF Model:</span>
                    <span className="text-cyan-400 font-mono font-bold text-sm">
                      {item.stocker_projected_base !== null && item.stocker_projected_base !== undefined ? `${item.stocker_projected_base}%` : 'N/A'}
                    </span>
                  </div>
                  <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800/40">
                    <span className="text-slate-400 block mb-1">Current Quarterly Run-Rate:</span>
                    <span className="text-emerald-400 font-mono font-bold text-sm">
                      {item.current_run_rate_value !== null && item.current_run_rate_value !== undefined ? `${item.current_run_rate_value}% (${item.current_run_rate_period || 'Latest Q'})` : 'Tracking'}
                    </span>
                  </div>
                </div>

                {item.stocker_assessment && (
                  <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/40 p-3 rounded-xl border border-slate-800/40">
                    {item.stocker_assessment}
                  </p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-slate-950/60 p-6 rounded-2xl border border-slate-800 text-center text-xs text-slate-400">
            No guidance vs projection triangulation items compiled yet.
          </div>
        )}
      </div>

      {/* 3. Capital Allocation Quality & Governance Watch */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Capital Allocation */}
        <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-4">
          <div className="flex items-center gap-2.5 border-b border-slate-800 pb-3">
            <div className="w-8 h-8 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center border border-amber-500/30">
              <Activity className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white">Capital Allocation & Capex Quality</h4>
              <p className="text-[11px] text-slate-400">Cash reinvestment, CWIP efficiency, and shareholder payout discipline</p>
            </div>
          </div>

          <div className="space-y-3 text-xs text-slate-300">
            {capitalAlloc?.capex_efficiency && (
              <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800/60 space-y-1">
                <span className="text-[10px] text-amber-400 uppercase tracking-wider font-bold block">Capex & CWIP Conversion:</span>
                <p className="leading-relaxed">{capitalAlloc.capex_efficiency}</p>
              </div>
            )}
            {capitalAlloc?.shareholder_returns && (
              <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800/60 space-y-1">
                <span className="text-[10px] text-emerald-400 uppercase tracking-wider font-bold block">Cash Flow & Payout Quality:</span>
                <p className="leading-relaxed">{capitalAlloc.shareholder_returns}</p>
              </div>
            )}
            {!capitalAlloc?.capex_efficiency && !capitalAlloc?.shareholder_returns && (
              <p className="text-slate-400 italic">Capital allocation metrics have not yet been synthesized from available financial cash flows.</p>
            )}
          </div>
        </div>

        {/* Governance & Accounting Watch */}
        <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-4">
          <div className="flex items-center gap-2.5 border-b border-slate-800 pb-3">
            <div className="w-8 h-8 rounded-xl bg-rose-500/20 text-rose-400 flex items-center justify-center border border-rose-500/30">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white">Governance & Accounting Watch</h4>
              <p className="text-[11px] text-slate-400">Auditor observations, working capital anomalies, and legal contingencies</p>
            </div>
          </div>

          <div className="space-y-3 text-xs text-slate-300">
            {governanceWatch?.working_capital_anomalies && (
              <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800/60 space-y-1">
                <span className="text-[10px] text-cyan-400 uppercase tracking-wider font-bold block">Working Capital Health:</span>
                <p className="leading-relaxed">{governanceWatch.working_capital_anomalies}</p>
              </div>
            )}
            {governanceWatch?.regulatory_or_legal_risks && governanceWatch.regulatory_or_legal_risks.length > 0 && (
              <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800/60 space-y-1">
                <span className="text-[10px] text-rose-400 uppercase tracking-wider font-bold block">Regulatory & Legal Watch:</span>
                <ul className="space-y-1">
                  {governanceWatch.regulatory_or_legal_risks.map((r, rIdx) => (
                    <li key={rIdx} className="flex items-start gap-1.5">
                      <span className="w-1 h-1 rounded-full bg-rose-400 shrink-0 mt-1.5" />
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {!governanceWatch?.working_capital_anomalies && (!governanceWatch?.regulatory_or_legal_risks || governanceWatch.regulatory_or_legal_risks.length === 0) && (
              <p className="text-slate-400 italic">No significant auditor qualifications or forensic red flags identified.</p>
            )}
          </div>
        </div>

      </div>

    </div>
  );
};
