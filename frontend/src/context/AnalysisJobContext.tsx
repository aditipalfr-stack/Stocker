import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { AnalysisJob, startDocIntelligenceJob, fetchAnalysisJob, fetchAllAnalysisJobs } from '../api';

interface AnalysisJobContextType {
  jobs: Record<string, AnalysisJob>;
  activeJobs: AnalysisJob[];
  completedNotification: AnalysisJob | null;
  dismissNotification: () => void;
  startAnalysis: (symbol: string) => Promise<AnalysisJob>;
  getJobForSymbol: (symbol: string) => AnalysisJob | undefined;
  requestNotificationPermission: () => Promise<NotificationPermission | null>;
}

const AnalysisJobContext = createContext<AnalysisJobContextType | null>(null);

export const AnalysisJobProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [jobs, setJobs] = useState<Record<string, AnalysisJob>>({});
  const [completedNotification, setCompletedNotification] = useState<AnalysisJob | null>(null);
  const activeJobSymbolsRef = useRef<Set<string>>(new Set());
  const pollingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Helper to trigger system / browser notification
  const triggerBrowserNotification = (job: AnalysisJob) => {
    if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted') {
      try {
        new Notification(`Stocker: AI Analysis Ready`, {
          body: `Fundamental extraction for ${job.company_name} (${job.symbol}) is complete!`,
          icon: '/favicon.png',
        });
      } catch (err) {
        console.warn('Browser notification failed:', err);
      }
    }
  };

  const requestNotificationPermission = async (): Promise<NotificationPermission | null> => {
    if (typeof window !== 'undefined' && 'Notification' in window) {
      if (Notification.permission === 'default') {
        return await Notification.requestPermission();
      }
      return Notification.permission;
    }
    return null;
  };

  // Poll active jobs
  const pollActiveJobs = useCallback(async () => {
    const activeSymbols = Array.from(activeJobSymbolsRef.current);
    if (activeSymbols.length === 0) {
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
      return;
    }

    try {
      const serverJobs = await fetchAllAnalysisJobs();
      setJobs(prev => {
        const next = { ...prev };
        for (const job of serverJobs) {
          const sym = job.symbol.toUpperCase();
          const oldJob = prev[sym];
          next[sym] = job;

          if (job.status === 'completed' || job.status === 'failed') {
            activeJobSymbolsRef.current.delete(sym);
            if (oldJob && oldJob.status === 'running' && job.status === 'completed') {
              setCompletedNotification(job);
              triggerBrowserNotification(job);
            }
          }
        }
        return next;
      });
    } catch (e) {
      console.warn('Failed to poll analysis jobs:', e);
    }
  }, []);

  const ensurePolling = useCallback(() => {
    if (!pollingTimerRef.current) {
      pollingTimerRef.current = setInterval(pollActiveJobs, 1500);
      void pollActiveJobs();
    }
  }, [pollActiveJobs]);

  // Initial fetch of jobs on mount
  useEffect(() => {
    fetchAllAnalysisJobs()
      .then(serverJobs => {
        setJobs(prev => {
          const next = { ...prev };
          for (const j of serverJobs) {
            const sym = j.symbol.toUpperCase();
            next[sym] = j;
            if (j.status === 'running' || j.status === 'queued') {
              activeJobSymbolsRef.current.add(sym);
            }
          }
          return next;
        });
        if (serverJobs.some(j => j.status === 'running' || j.status === 'queued')) {
          ensurePolling();
        }
      })
      .catch(() => {});

    return () => {
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    };
  }, [ensurePolling]);

  const startAnalysis = async (symbol: string): Promise<AnalysisJob> => {
    const cleanSym = symbol.toUpperCase().trim();
    // Pre-request notification permission in user-gesture context
    void requestNotificationPermission();

    const job = await startDocIntelligenceJob(cleanSym);
    setJobs(prev => ({ ...prev, [cleanSym]: job }));
    if (job.status === 'running' || job.status === 'queued') {
      activeJobSymbolsRef.current.add(cleanSym);
      ensurePolling();
    }
    return job;
  };

  const getJobForSymbol = (symbol: string): AnalysisJob | undefined => {
    return jobs[symbol.toUpperCase().trim()];
  };

  const dismissNotification = () => {
    setCompletedNotification(null);
  };

  const activeJobs = Object.values(jobs).filter(
    j => j.status === 'running' || j.status === 'queued'
  );

  return (
    <AnalysisJobContext.Provider
      value={{
        jobs,
        activeJobs,
        completedNotification,
        dismissNotification,
        startAnalysis,
        getJobForSymbol,
        requestNotificationPermission
      }}
    >
      {children}
    </AnalysisJobContext.Provider>
  );
};

export const useAnalysisJobs = () => {
  const ctx = useContext(AnalysisJobContext);
  if (!ctx) {
    throw new Error('useAnalysisJobs must be used within an AnalysisJobProvider');
  }
  return ctx;
};
