import React, { useState, useEffect } from 'react';
import { 
  StockSummary, StockDetail, ComparisonItem 
} from './types';
import { 
  fetchStocks, fetchStockDetail, scrapeNewStock, compareStocks 
} from './api';
import { Navbar } from './components/Navbar';
import { DashboardOverview } from './components/DashboardOverview';
import { StockDetailView } from './components/StockDetailView';
import { StockComparison } from './components/StockComparison';
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
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const showToast = (text: string, type: 'success' | 'error' = 'success') => {
    setToastMessage({ text, type });
    setTimeout(() => setToastMessage(null), 4000);
  };

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
      setSelectedStockSymbol(symbol);
      setSelectedStockDetail(detail);
      setActiveTab('detail');
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

  // Handle Search / Scrape on demand
  const handleSearchOrScrape = async (symbol: string) => {
    try {
      showToast(`Fetching ${symbol} from Screener.in...`, 'success');
      const res = await scrapeNewStock(symbol);
      showToast(res.message, 'success');
      await loadStocks();
      await loadStockDetail(symbol);
    } catch (e: any) {
      showToast(e.message || `Failed to fetch ${symbol}`, 'error');
    }
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
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-emerald-500 selection:text-white">
      
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
        onSearchOrScrape={handleSearchOrScrape}
        isLoading={isLoading}
        selectedStockSymbol={selectedStockSymbol}
        compareCount={selectedCompareSymbols.length}
      />

      {/* Main App Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 lg:px-8 pt-6">
        
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
            onScrapeRefresh={() => handleSearchOrScrape(selectedStockDetail.symbol)}
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
      <footer className="border-t border-slate-900 bg-slate-950/80 py-6 px-4 text-center text-xs text-slate-500 font-mono">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>Stocker Decision Platform • Powered by Raw Screener Data & DCF Engine</span>
          <span>Nifty 500 Fundamental Ingestion Ready</span>
        </div>
      </footer>

    </div>
  );
}

export default App;

