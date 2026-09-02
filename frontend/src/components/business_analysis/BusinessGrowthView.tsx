import React from 'react';
import { BusinessAnalysisIntelligence } from '../../types';
import { 
  Layers, TrendingUp, DollarSign, Activity, 
  ExternalLink, ShieldCheck, Target, BarChart3, Building
} from 'lucide-react';
import { DataOriginBadge } from '../ui/DataOriginBadge';

interface BusinessGrowthViewProps {
  docIntel: BusinessAnalysisIntelligence;
  companyName: string;
}

export const BusinessGrowthView: React.FC<BusinessGrowthViewProps> = ({ docIntel, companyName }) => {
  const bzQuality = docIntel.business_quality;
  const compPos = docIntel.competitive_position;
  const demandMomentum = docIntel.demand_momentum;
  const growthDrivers = docIntel.growth_drivers || [];
  const kpiEvolution = docIntel.operational_kpi_evolution || [];

  return (
    <div className="space-y-8">

      {/* 1. Business Model & How Company Makes Money */}
      <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-cyan-500/20 text-cyan-400 flex items-center justify-center border border-cyan-500/30 shrink-0">
              <Building className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-base font-bold text-white flex items-center gap-2">
                <span>Business Model & Monetization Architecture</span>
                <DataOriginBadge origin="ai_interpretation" />
              </h4>
              <p className="text-xs text-slate-400">Core value proposition, revenue streams, and customer engagement</p>
            </div>
          </div>
        </div>

        <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800 space-y-3">
          <p className="text-sm text-slate-200 leading-relaxed">
            {bzQuality?.business_model_summary || `${companyName} generates revenue across core operational segments, monetizing through contractual volumes, customer subscriptions, and ongoing value-added services.`}
          </p>
        </div>

        {/* Segment & Geography Mix Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          
          {/* Segment Mix */}
          <div className="bg-slate-950/80 p-5 rounded-2xl border border-slate-800/80 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-2.5">
              <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-cyan-400" />
                <span>Segment Revenue Breakdown</span>
              </span>
              <span className="text-[10px] text-slate-500 font-mono">Reported Mix</span>
            </div>

            {bzQuality?.segment_mix && bzQuality.segment_mix.length > 0 ? (
              <div className="space-y-2">
                {bzQuality.segment_mix.map((seg, idx) => (
                  <div key={idx} className="flex items-center justify-between text-xs p-2 rounded-xl bg-slate-900/60 border border-slate-800/40">
                    <span className="text-slate-300 font-medium">{seg.segment || `Segment ${idx + 1}`}</span>
                    <span className="text-cyan-400 font-mono font-bold">
                      {seg.share_pct !== undefined ? `${seg.share_pct}%` : (seg.growth_pct !== undefined ? `+${seg.growth_pct}% YoY` : 'Reported')}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">Segment mix synthesized from core operational verticals in filings.</p>
            )}
          </div>

          {/* Geography / Market Mix */}
          <div className="bg-slate-950/80 p-5 rounded-2xl border border-slate-800/80 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-2.5">
              <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <Target className="w-3.5 h-3.5 text-emerald-400" />
                <span>Geographical / Market Reach</span>
              </span>
              <span className="text-[10px] text-slate-500 font-mono">Footprint</span>
            </div>

            {bzQuality?.geography_mix && bzQuality.geography_mix.length > 0 ? (
              <div className="space-y-2">
                {bzQuality.geography_mix.map((geo, idx) => (
                  <div key={idx} className="flex items-center justify-between text-xs p-2 rounded-xl bg-slate-900/60 border border-slate-800/40">
                    <span className="text-slate-300 font-medium">{geo.region || `Region ${idx + 1}`}</span>
                    <span className="text-emerald-400 font-mono font-bold">
                      {geo.share_pct !== undefined ? `${geo.share_pct}%` : 'Active Market'}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">Broad domestic and international footprint across core operational regions.</p>
            )}
          </div>

        </div>
      </div>

      {/* 2. Demand Momentum & Volume Indicators */}
      <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30 shrink-0">
              <TrendingUp className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-base font-bold text-white flex items-center gap-2">
                <span>Demand Momentum, Volumes & Order Book</span>
                <DataOriginBadge origin="ai_interpretation" />
              </h4>
              <p className="text-xs text-slate-400">Order pipeline, volume growth, capacity utilization, and client demand indicators</p>
            </div>
          </div>
        </div>

        {demandMomentum?.summary && (
          <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800 space-y-2">
            <p className="text-sm text-slate-200 leading-relaxed font-normal">{demandMomentum.summary}</p>
          </div>
        )}

        {/* Company-Specific Metrics & Segment Trends */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {demandMomentum?.company_specific_metrics && demandMomentum.company_specific_metrics.length > 0 && (
            <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800 space-y-3">
              <h5 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <Activity className="w-3.5 h-3.5 text-cyan-400" />
                <span>Key Operational Volume Indicators</span>
              </h5>
              <div className="space-y-2">
                {demandMomentum.company_specific_metrics.map((m, idx) => (
                  <div key={idx} className="flex items-center justify-between text-xs p-2.5 rounded-xl bg-slate-900/60 border border-slate-800/40">
                    <span className="text-slate-300 font-medium">{String(m.metric || m.name || `Metric ${idx+1}`)}</span>
                    <span className="text-cyan-400 font-mono font-bold">{String(m.value || m.val || '')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {demandMomentum?.segment_trends && demandMomentum.segment_trends.length > 0 && (
            <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800 space-y-3">
              <h5 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <BarChart3 className="w-3.5 h-3.5 text-emerald-400" />
                <span>Segment Growth Trajectories</span>
              </h5>
              <div className="space-y-2">
                {demandMomentum.segment_trends.map((s, idx) => (
                  <div key={idx} className="flex items-center justify-between text-xs p-2.5 rounded-xl bg-slate-900/60 border border-slate-800/40">
                    <span className="text-slate-300 font-medium">{String(s.segment || s.name || `Vertical ${idx+1}`)}</span>
                    <span className="text-emerald-400 font-mono font-medium">{String(s.trend || s.growth || 'Expanding')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 3. Operational KPI Evolution (Time Series) */}
      <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-amber-500/20 text-amber-400 flex items-center justify-center border border-amber-500/30 shrink-0">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-base font-bold text-white flex items-center gap-2">
                <span>Operational KPI Evolution (Multi-Filing Time Series)</span>
                <span className="bg-slate-900 text-amber-400 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-slate-800">
                  {kpiEvolution.length} tracked KPIs
                </span>
              </h4>
              <p className="text-xs text-slate-400">Chronological trajectory of core non-financial volume, capacity, and operational metrics</p>
            </div>
          </div>
        </div>

        {kpiEvolution.length > 0 ? (
          <div className="space-y-4">
            {kpiEvolution.map((kpi, idx) => {
              const trajBg = 
                kpi.trajectory === 'Expanding' || kpi.trajectory === 'Improving' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                kpi.trajectory === 'Contracting' || kpi.trajectory === 'Deteriorating' ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' :
                'bg-amber-500/10 text-amber-400 border-amber-500/20';

              return (
                <div key={idx} className="bg-slate-950 p-5 rounded-2xl border border-slate-800 space-y-4 hover:border-slate-700 transition-all">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-900 pb-3">
                    <div className="flex items-center gap-2.5">
                      <span className="text-sm font-bold text-white">{kpi.metric_name}</span>
                      <span className={`text-[10px] font-semibold px-2.5 py-0.5 rounded-full border ${trajBg}`}>
                        {kpi.trajectory}
                      </span>
                    </div>
                    {kpi.latest_vs_prior_change && (
                      <span className="text-xs font-mono font-bold text-cyan-400">
                        {kpi.latest_vs_prior_change}
                      </span>
                    )}
                  </div>

                  {/* Chronological Series Points */}
                  {kpi.data_points && kpi.data_points.length > 0 && (
                    <div className="flex items-center gap-2 overflow-x-auto pb-2 pt-1">
                      {kpi.data_points.map((dp, pIdx) => (
                        <div key={pIdx} className="bg-slate-900/90 border border-slate-800 px-3 py-2 rounded-xl shrink-0 space-y-1">
                          <span className="text-[10px] font-mono text-slate-400 block">{dp.period}</span>
                          <span className="text-xs font-bold font-mono text-emerald-400 block">{dp.stated_value}</span>
                          {dp.doc_title && (
                            <span className="text-[9px] text-slate-500 block truncate max-w-[120px]">{dp.doc_title}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {kpi.insight && (
                    <p className="text-xs text-slate-300 leading-relaxed italic bg-slate-900/40 p-3 rounded-xl border border-slate-800/40">
                      {kpi.insight}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="bg-slate-950/60 p-6 rounded-2xl border border-slate-800 text-center text-xs text-slate-400">
            No inter-document operational KPI trends compiled yet. Run live AI analysis to extract chronological series.
          </div>
        )}
      </div>

      {/* 4. Capacity Expansion, Capex & Growth Pipeline */}
      <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-cyan-500/20 text-cyan-400 flex items-center justify-center border border-cyan-500/30 shrink-0">
              <Target className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-base font-bold text-white flex items-center gap-2">
                <span>Capacity Expansion, Capex & Growth Pipeline</span>
                <span className="bg-slate-900 text-cyan-400 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-slate-800">
                  {growthDrivers.length} initiatives
                </span>
              </h4>
              <p className="text-xs text-slate-400">Upcoming plant additions, product launches, acquisitions, and strategic capital outlays</p>
            </div>
          </div>
        </div>

        {growthDrivers.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {growthDrivers.map((driver, idx) => (
              <div key={idx} className="bg-slate-950 p-5 rounded-2xl border border-slate-800 space-y-3 hover:border-slate-700 transition-all flex flex-col justify-between">
                <div className="space-y-2.5">
                  <div className="flex items-start justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="bg-cyan-500/10 text-cyan-400 text-[11px] font-semibold px-2.5 py-0.5 rounded-full border border-cyan-500/20">
                        {driver.driver_type || 'Structural Driver'}
                      </span>
                      {driver.is_one_off && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40">
                          ONE-OFF
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                      {driver.execution_status || 'In Progress'}
                    </span>
                  </div>

                  <h5 className="text-sm font-bold text-white leading-snug">{driver.driver_title}</h5>
                  <p className="text-xs text-slate-300 leading-relaxed">{driver.description}</p>
                </div>

                <div className="pt-3 border-t border-slate-900 space-y-2">
                  <div className="flex items-center justify-between text-xs font-mono">
                    {driver.stated_outlay_or_value && (
                      <span className="text-amber-400 font-bold">Outlay: {driver.stated_outlay_or_value}</span>
                    )}
                    {driver.target_timeline && (
                      <span className="text-slate-400">Timeline: {driver.target_timeline}</span>
                    )}
                  </div>

                  {driver.source_url && (
                    <div className="flex items-center justify-end">
                      <a
                        href={driver.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[10px] text-slate-400 hover:text-cyan-400 flex items-center gap-1 transition-colors"
                      >
                        <span>Evidence Filing</span>
                        {driver.source_page && <span className="font-mono text-cyan-400">p.{driver.source_page}</span>}
                        <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-slate-950/60 p-6 rounded-2xl border border-slate-800 text-center text-xs text-slate-400">
            No specific capacity expansion roadmaps extracted yet.
          </div>
        )}
      </div>

      {/* 5. Competitive Position & Economic Moat */}
      <div className="glass-panel rounded-3xl p-6 md:p-8 border border-slate-800 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30 shrink-0">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-base font-bold text-white flex items-center gap-2">
                <span>Competitive Position & Economic Moat</span>
                <DataOriginBadge origin="ai_interpretation" />
              </h4>
              <p className="text-xs text-slate-400">Moat durability, pricing power, scale advantages, and competitive threats</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Moat Type:</span>
            <span className="text-xs font-bold px-3 py-1 rounded-full border border-indigo-500/30 bg-indigo-500/10 text-indigo-400">
              {compPos?.moat_type || 'Narrow / Scale Advantage'}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          
          {/* Key Moats & Differentiators */}
          <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800 space-y-3">
            <h5 className="text-xs font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Competitive Advantages</span>
            </h5>
            <ul className="space-y-2 text-xs text-slate-300">
              {compPos?.key_advantages && compPos.key_advantages.length > 0 ? (
                compPos.key_advantages.map((adv, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0 mt-1.5" />
                    <span>{adv}</span>
                  </li>
                ))
              ) : (
                <li className="text-slate-400 italic">Established market position with strong brand distribution and customer relationships.</li>
              )}
            </ul>
          </div>

          {/* Competitive Threats & Pricing Power */}
          <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800 space-y-3">
            <h5 className="text-xs font-bold text-rose-400 uppercase tracking-wider flex items-center gap-1.5">
              <Target className="w-4 h-4 text-rose-400" />
              <span>Competitive Threats & Pricing Power</span>
            </h5>
            {compPos?.pricing_power_assessment && (
              <p className="text-xs text-slate-300 leading-relaxed">
                <strong className="text-white">Pricing Power:</strong> {compPos.pricing_power_assessment}
              </p>
            )}
            <ul className="space-y-2 text-xs text-slate-300">
              {compPos?.competitive_threats && compPos.competitive_threats.length > 0 ? (
                compPos.competitive_threats.map((threat, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-400 shrink-0 mt-1.5" />
                    <span>{threat}</span>
                  </li>
                ))
              ) : (
                <li className="text-slate-400 italic">Monitored for competitive pricing aggression and new market entrants.</li>
              )}
            </ul>
          </div>

        </div>
      </div>

    </div>
  );
};
