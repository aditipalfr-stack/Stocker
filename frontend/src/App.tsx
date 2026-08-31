import React, { useCallback, useEffect, useRef, useState } from 'react';
import { 
  StockSummary, StockDetail, ComparisonItem, ResearchLifecycleStatus
} from './types';
import { 
  addCompany, compareStocks, discoverFilings, fetchResearchStatus,
  fetchStocks, fetchStockDetail, scrapeNewStock, triggerFinancialVerification
} from './api';
import { Navbar } from './components/Navbar';
import { DashboardOverview } from './components/DashboardOverview';
import { StockDetailView } from './components/StockDetailView';
import { StockComparison } from './components/StockComparison';
import { GlossaryDrawer } from './components/ui/GlossaryDrawer';
import { RefreshCw, AlertCircle, CheckCircle2 } from 'lucide-react';

export function App() {
  const [activeTab, setActiveTab] = useState<'overview' | 'detail' | 'compare'>('overview');
  const [stocks, setStocks] = useState<StockSummary[]>([]);
  const [selectedStockSymbol, setSelectedStockSymbol] = useState<string>('RELIANCE');
  const [selectedStockDetail, setSelectedStockDetail] = useState<StockDetail | null>(null);
  
  const [selectedCompareSymbols, setSelectedCompareSymbols] = useState<string[]>(['HDFCBANK', 'ICICIBANK', 'TCS']);
  const [comparisonData, setComparisonData] = useState<ComparisonItem[]>([]);
  
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isDetailLoading, setIsDetailLoading] = useState<boolean>(false);
  const [isFinancialRefreshing, setIsFinancialRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const [isGlossaryOpen, setIsGlossaryOpen] = useState(false);
  const [researchStatus, setResearchStatus] = useState<ResearchLifecycleStatus | null>(null);
  const [researchStatusLoading, setResearchStatusLoading] = useState(false);
  const [researchStatusError, setResearchStatusError] = useState<string | null>(null);
  const [filingDiscoveryState, setFilingDiscoveryState] = useState<'idle' | 'running' | 'success' | 'error'>('idle');
  const [verificationState, setVerificationState] = useState<'idle' | 'running' | 'success' | 'error'>('idle');
  const selectedSymbolRef = useRef(selectedStockSymbol);
  const statusRequestsRef = useRef<Record<string, Promise<ResearchLifecycleStatus>>>({});

  const showToast = (text: string, type: 'success' | 'error' = 'success') => {
    setToastMessage({ text, type });
    setTimeout(() => setToastMessage(null), 4000);
  };

  const refreshResearchStatus = useCallback(async (symbol: string) => {
    const canonicalSymbol = symbol.toUpperCase();
    setResearchStatusLoading(true);
    setResearchStatusError(null);
    let request = statusRequestsRef.current[canonicalSymbol];
    if (!request) {
      request = fetchResearchStatus(canonicalSymbol);
      statusRequestsRef.current[canonicalSymbol] = request;
    }
    try {
      const nextStatus = await request;
      if (selectedSymbolRef.current === canonicalSymbol) setResearchStatus(nextStatus);
    } catch (err: any) {
      if (selectedSymbolRef.current === canonicalSymbol) setResearchStatusError(err.message || 'Failed to load research progress');
    } finally {
      if (statusRequestsRef.current[canonicalSymbol] === request) delete statusRequestsRef.current[canonicalSymbol];
      if (selectedSymbolRef.current === canonicalSymbol) setResearchStatusLoading(false);
    }
  }, []);

  // Load initial stock list
  const loadStocks = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchStocks();
      setStocks(data);
      if (data.length > 0 && !selectedStockDetail) {
        loadStockDetail(data[0].symbol);
      }
    } catch (e: any) {
      setError(e.message || 'Failed to load stocks from server');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadStocks();
  }, []);

  // Load deep dive detail
  const loadStockDetail = async (symbol: string) => {
    setIsDetailLoading(true);
    try {
      const detail = await fetchStockDetail(symbol);
      const canonicalSymbol = detail.symbol.toUpperCase();
      selectedSymbolRef.current = canonicalSymbol;
      setSelectedStockSymbol(canonicalSymbol);
      setSelectedStockDetail(detail);
      setResearchStatus(null);
      setResearchStatusError(null);
      setFilingDiscoveryState('idle');
      setVerificationState('idle');
      setActiveTab('detail');
      void refreshResearchStatus(canonicalSymbol);
    } catch (e: any) {
      showToast(`Failed to load details for ${symbol}: ${e.message}`, 'error');
    } finally {
      setIsDetailLoading(false);
    }
  };

  // Load comparison data
  const loadComparison = async (symbols: string[]) => {
    if (symbols.length === 0) {
      setComparisonData([]);
      return;
    }
    try {
      const data = await compareStocks(symbols);
      setComparisonData(data);
    } catch (e: any) {
      showToast(`Failed to compare stocks: ${e.message}`, 'error');
    }
  };

  useEffect(() => {
    if (selectedCompareSymbols.length > 0) {
      loadComparison(selectedCompareSymbols);
    }
  }, [selectedCompareSymbols]);

  const runFilingDiscovery = async (symbol: string) => {
    if (selectedSymbolRef.current === symbol) setFilingDiscoveryState('running');
    try {
      const result = await discoverFilings(symbol);
      if (selectedSymbolRef.current === symbol) {
        setFilingDiscoveryState('success');
        setResearchStatus(result.research_status);
      }
    } catch (e: any) {
      if (selectedSymbolRef.current === symbol) {
        setFilingDiscoveryState('error');
        showToast(e.message || `Filing discovery failed for ${symbol}. Financial analysis remains available.`, 'error');
      }
    } finally {
      await refreshResearchStatus(symbol);
    }
  };

  const runOfficialVerification = async (symbol: string) => {
    if (selectedSymbolRef.current === symbol) setVerificationState('running');
    try {
      await triggerFinancialVerification(symbol);
      if (selectedSymbolRef.current === symbol) setVerificationState('success');
    } catch (e: any) {
      if (selectedSymbolRef.current === symbol) {
        setVerificationState('error');
        showToast(e.message || `Official verification failed for ${symbol}. Financial analysis remains available.`, 'error');
      }
    } finally {
      await refreshResearchStatus(symbol);
    }
  };

  const handleAddCompany = async (query: string) => {
    const response = await addCompany(query);
    const canonicalSymbol = response.symbol.toUpperCase();
    selectedSymbolRef.current = canonicalSymbol;
    setSelectedStockSymbol(canonicalSymbol);
    setSelectedStockDetail(response.stock);
    setResearchStatus(response.research_status);
    setResearchStatusError(null);
    setFilingDiscoveryState('idle');
    setVerificationState('idle');
    setActiveTab('detail');
    showToast(response.already_existed ? `${response.company_name} is already in Stocker.` : response.message, 'success');
    void fetchStocks().then(setStocks).catch(() => {});
    void runFilingDiscovery(canonicalSymbol);
    void runOfficialVerification(canonicalSymbol);
  };

  const handleCanonicalRefresh = async (symbol: string) => {
    setIsFinancialRefreshing(true);
    try {
      const response = await scrapeNewStock(symbol);
      const updatedStock = response.stock || await fetchStockDetail(symbol);
      setSelectedStockDetail(updatedStock);
      showToast(response.message, 'success');
      void fetchStocks().then(setStocks).catch(() => {});
      await refreshResearchStatus(updatedStock.symbol);
    } catch (e: any) {
      showToast(e.message || `Failed to refresh financial data for ${symbol}`, 'error');
    } finally {
      setIsFinancialRefreshing(false);
    }
  };

  const handleStockUpdated = (updatedStock: StockDetail) => {
    if (selectedSymbolRef.current === updatedStock.symbol.toUpperCase()) setSelectedStockDetail(updatedStock);
    void fetchStocks().then(setStocks).catch(() => {});
  };

  // Toggle compare symbol
  const handleToggleCompare = (symbol: string) => {
    if (selectedCompareSymbols.includes(symbol)) {
      setSelectedCompareSymbols(selectedCompareSymbols.filter(s => s !== symbol));
    } else {
      if (selectedCompareSymbols.length >= 5) {
        showToast('Maximum 5 stocks can be compared simultaneously', 'error');
        return;
      }
      setSelectedCompareSymbols([...selectedCompareSymbols, symbol]);
    }
  };

  const handleRemoveCompareSymbol = (symbol: string) => {
    setSelectedCompareSymbols(selectedCompareSymbols.filter(s => s !== symbol));
  };

  const handleAddCompareSymbol = (symbol: string) => {
    if (!selectedCompareSymbols.includes(symbol)) {
      if (selectedCompareSymbols.length >= 5) {
        showToast('Maximum 5 stocks can be compared simultaneously', 'error');
        return;
      }
      setSelectedCompareSymbols([...selectedCompareSymbols, symbol]);
    }
  };

  return (
    <div className="min-h-screen bg-page text-primary flex flex-col selection:bg-emerald-500 selection:text-white">
      
      {/* Toast Notification Banner */}
      {toastMessage && (
        <div className={`fixed bottom-6 right-6 z-50 px-4 py-3 rounded-2xl shadow-2xl border flex items-center gap-2.5 transition-all text-xs font-semibold ${
          toastMessage.type === 'success'
            ? 'bg-slate-900/95 text-emerald-400 border-emerald-500/50 shadow-emerald-500/10'
            : 'bg-slate-900/95 text-rose-400 border-rose-500/50 shadow-rose-500/10'
        }`}>
          {toastMessage.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          ) : (
            <AlertCircle className="w-4 h-4 text-rose-400" />
          )}
          <span>{toastMessage.text}</span>
        </div>
      )}

      {/* Main Navbar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onAddCompany={handleAddCompany}
        onOpenExisting={loadStockDetail}
        isLoading={isLoading}
        selectedStockSymbol={selectedStockSymbol}
        compareCount={selectedCompareSymbols.length}
        onOpenGlossary={() => setIsGlossaryOpen(true)}
      />

      <GlossaryDrawer isOpen={isGlossaryOpen} onClose={() => setIsGlossaryOpen(false)} />

      {/* Main App Body */}
      <main className="layout-wide flex-1 pt-5 lg:pt-6">
        
        {/* Global Loading Spinner */}
        {isLoading && (
          <div className="py-20 text-center space-y-3">
            <RefreshCw className="w-8 h-8 text-emerald-500 animate-spin mx-auto" />
            <p className="text-xs text-slate-400 font-mono">Loading Screener Financial Data & Decision Engine...</p>
          </div>
        )}

        {/* Global Error Banner */}
        {error && !isLoading && (
          <div className="bg-rose-950/40 border border-rose-800 p-6 rounded-3xl text-center space-y-3 max-w-xl mx-auto my-12">
            <AlertCircle className="w-8 h-8 text-rose-400 mx-auto" />
            <h3 className="text-base font-bold text-rose-200">Unable to Connect to Backend API</h3>
            <p className="text-xs text-slate-300">{error}</p>
            <button
              onClick={loadStocks}
              className="bg-rose-600 hover:bg-rose-500 text-white font-bold px-4 py-1.5 rounded-xl text-xs"
            >
              Retry Connection
            </button>
          </div>
        )}

        {/* Screen 1: Dashboard Overview */}
        {!isLoading && !error && activeTab === 'overview' && (
          <DashboardOverview
            stocks={stocks}
            onSelectStock={loadStockDetail}
            selectedCompareSymbols={selectedCompareSymbols}
            onToggleCompare={handleToggleCompare}
            onOpenCompare={() => setActiveTab('compare')}
          />
        )}

        {/* Screen 2: Deep Dive Stock Detail */}
        {!isLoading && !error && activeTab === 'detail' && selectedStockDetail && (
          <StockDetailView
            stock={selectedStockDetail}
            onBack={() => setActiveTab('overview')}
            onScrapeRefresh={() => handleCanonicalRefresh(selectedStockDetail.symbol)}
            isFinancialRefreshing={isFinancialRefreshing}
            researchStatus={researchStatus}
            researchStatusLoading={researchStatusLoading}
            researchStatusError={researchStatusError}
            filingDiscoveryState={filingDiscoveryState}
            verificationState={verificationState}
            onRetryFilings={() => runFilingDiscovery(selectedStockDetail.symbol)}
            onRetryVerification={() => runOfficialVerification(selectedStockDetail.symbol)}
            onRefreshResearchStatus={() => refreshResearchStatus(selectedStockDetail.symbol)}
            onStockUpdated={handleStockUpdated}
          />
        )}

        {/* Screen 3: Comparison Arena */}
        {!isLoading && !error && activeTab === 'compare' && (
          <StockComparison
            comparisonData={comparisonData}
            onRemoveSymbol={handleRemoveCompareSymbol}
            onSelectStock={loadStockDetail}
            onBack={() => setActiveTab('overview')}
            availableSymbols={stocks.map(s => s.symbol)}
            onAddSymbol={handleAddCompareSymbol}
          />
        )}

      </main>

      {/* Institutional Footer */}
      <footer className="border-t border-theme bg-panel py-5 text-center text-xs text-muted font-mono">
        <div className="layout-wide flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>Stocker Decision Platform • Powered by Raw Screener Data & DCF Engine</span>
          <span>Nifty 500 Fundamental Ingestion Ready</span>
        </div>
      </footer>

    </div>
  );
}

export default App;
