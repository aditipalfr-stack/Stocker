import React, { useEffect } from 'react';
import { Sparkles, CheckCircle2, ArrowRight, X } from 'lucide-react';
import { useAnalysisJobs } from '../../context/AnalysisJobContext';

interface AnalysisNotificationToastProps {
  onOpenStock: (symbol: string) => void;
}

export const AnalysisNotificationToast: React.FC<AnalysisNotificationToastProps> = ({ onOpenStock }) => {
  const { completedNotification, dismissNotification } = useAnalysisJobs();

  useEffect(() => {
    if (!completedNotification) return;
    const timer = setTimeout(() => {
      dismissNotification();
    }, 9000);
    return () => clearTimeout(timer);
  }, [completedNotification, dismissNotification]);

  if (!completedNotification) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 max-w-sm w-full animate-in slide-in-from-bottom-5 fade-in duration-300">
      <div className="bg-slate-900/95 backdrop-blur-md border border-emerald-500/40 rounded-2xl p-4 shadow-2xl shadow-emerald-950/40 flex items-start gap-3.5">
        <div className="w-9 h-9 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30 shrink-0 mt-0.5">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-xs font-bold text-white truncate">
              {completedNotification.symbol} • AI Analysis Ready
            </h4>
            <button
              onClick={dismissNotification}
              className="text-slate-400 hover:text-slate-200 p-0.5 rounded transition-colors"
              title="Dismiss"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <p className="text-[11px] text-slate-300 mt-0.5 line-clamp-1">
            {completedNotification.company_name} filings synthesized.
          </p>
          <div className="mt-2.5 flex items-center gap-2">
            <button
              onClick={() => {
                onOpenStock(completedNotification.symbol);
                dismissNotification();
              }}
              className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold px-3 py-1 rounded-lg text-xs flex items-center gap-1.5 shadow-md shadow-emerald-500/20 transition-all"
            >
              <span>View Dossier</span>
              <ArrowRight className="w-3 h-3" />
            </button>
            <button
              onClick={dismissNotification}
              className="text-slate-400 hover:text-slate-300 text-xs px-2 py-1"
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
