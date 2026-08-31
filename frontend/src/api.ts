import {
  AddCompanyResponse, BusinessAnalysisIntelligence, BusinessOutlookIntelligence,
  CompanyRegistryItem, CompanySearchResponse, ComparisonItem, DiscoverFilingsResponse,
  FinancialVerificationResponse, ProjectionAssumption, ProjectionResult,
  ResearchLifecycleStatus, SourceFilingsResponse, StockDetail, StockSummary
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

export async function fetchStocks(sector?: string, minScore?: number): Promise<StockSummary[]> {
  const params = new URLSearchParams();
  if (sector) params.append('sector', sector);
  if (minScore !== undefined) params.append('min_score', minScore.toString());
  
  const res = await fetch(`${API_BASE}/stocks?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to fetch stocks: ${res.statusText}`);
  return res.json();
}

export async function fetchStockDetail(symbol: string): Promise<StockDetail> {
  const res = await fetch(`${API_BASE}/stocks/${symbol}`);
  if (!res.ok) throw new Error(`Failed to fetch stock detail for ${symbol}`);
  return res.json();
}

export async function projectStock(symbol: string, assumptions: ProjectionAssumption): Promise<ProjectionResult> {
  const res = await fetch(`${API_BASE}/stocks/${symbol}/project`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(assumptions)
  });
  if (!res.ok) throw new Error(`Failed to calculate projection for ${symbol}`);
  return res.json();
}

export async function scrapeNewStock(symbol: string): Promise<{ success: boolean; message: string; stock: StockDetail }> {
  const res = await fetch(`${API_BASE}/stocks/scrape/${symbol}`, {
    method: 'POST'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to scrape stock' }));
    throw new Error(err.detail || 'Failed to scrape stock');
  }
  return res.json();
}

export async function compareStocks(symbols: string[]): Promise<ComparisonItem[]> {
  const res = await fetch(`${API_BASE}/stocks/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbols })
  });
  if (!res.ok) throw new Error('Failed to compare stocks');
  const data = await res.json();
  return data.comparison;
}

export async function fetchDocIntelligence(symbol: string): Promise<BusinessOutlookIntelligence | null> {
  const res = await fetch(`${API_BASE}/stocks/${encodeURIComponent(symbol)}/doc-intelligence`);
  if (!res.ok) return null;
  return res.json();
}

export async function fetchBusinessAnalysis(symbol: string): Promise<BusinessAnalysisIntelligence | null> {
  const res = await fetch(`${API_BASE}/stocks/${encodeURIComponent(symbol)}/business-analysis`);
  if (!res.ok) return null;
  return res.json();
}

export async function fetchSourceFilings(symbol: string): Promise<SourceFilingsResponse> {
  const res = await fetch(`${API_BASE}/stocks/${encodeURIComponent(symbol)}/source-filings`);
  if (!res.ok) throw new Error(`Failed to fetch source filings for ${symbol}`);
  return res.json();
}

export async function generateDocIntelligence(symbol: string): Promise<BusinessOutlookIntelligence> {
  const res = await fetch(`${API_BASE}/stocks/${symbol}/generate-doc-intelligence`, {
    method: 'POST'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to generate document intelligence' }));
    throw new Error(err.detail || 'Failed to generate document intelligence');
  }
  return res.json();
}

export interface AiStatusResult {
  configured: boolean;
  provider: string | null;
  status: 'active' | 'invalid_key' | 'quota_exceeded' | 'missing_key' | 'network_error' | 'error';
  key_preview: string | null;
  message: string;
}

export async function fetchAiStatus(): Promise<AiStatusResult> {
  const res = await fetch(`${API_BASE}/ai/status`);
  if (!res.ok) {
    throw new Error('Failed to fetch AI service status');
  }
  return res.json();
}

export async function configureAiKey(apiKey: string, provider: string = 'gemini'): Promise<AiStatusResult> {
  const res = await fetch(`${API_BASE}/ai/configure`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ api_key: apiKey, provider })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to configure AI key' }));
    throw new Error(err.detail || 'Failed to configure AI key');
  }
  return res.json();
}

export async function searchCompanies(query: string, limit: number = 10): Promise<CompanySearchResponse> {
  const params = new URLSearchParams({ q: query, limit: limit.toString() });
  const res = await fetch(`${API_BASE}/companies/search?${params.toString()}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to search companies' }));
    throw new Error(err.detail || 'Failed to search companies');
  }
  return res.json();
}

export async function addCompany(query: string): Promise<AddCompanyResponse> {
  const res = await fetch(`${API_BASE}/companies/add`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to add company to universe' }));
    throw new Error(err.detail || 'Failed to add company to universe');
  }
  return res.json();
}

export async function fetchResearchStatus(symbol: string): Promise<ResearchLifecycleStatus> {
  const res = await fetch(`${API_BASE}/stocks/${encodeURIComponent(symbol)}/research-status`);
  if (!res.ok) throw new Error(`Failed to fetch research status for ${symbol}`);
  return res.json();
}

export async function discoverFilings(symbol: string): Promise<DiscoverFilingsResponse> {
  const res = await fetch(`${API_BASE}/stocks/${encodeURIComponent(symbol)}/discover-filings`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to discover source filings' }));
    throw new Error(err.detail || `Failed to discover source filings for ${symbol}`);
  }
  return res.json();
}

export async function fetchRegisteredCompanies(activeOnly: boolean = false): Promise<CompanyRegistryItem[]> {
  const params = activeOnly ? '?active_only=true' : '';
  const res = await fetch(`${API_BASE}/companies${params}`);
  if (!res.ok) throw new Error('Failed to fetch registered companies');
  return res.json();
}

export async function fetchFinancialVerification(symbol: string): Promise<FinancialVerificationResponse> {
  const res = await fetch(`${API_BASE}/stocks/${encodeURIComponent(symbol)}/financial-verification`);
  if (!res.ok) throw new Error(`Failed to fetch financial verification for ${symbol}`);
  return res.json();
}

export async function triggerFinancialVerification(symbol: string): Promise<FinancialVerificationResponse> {
  const res = await fetch(`${API_BASE}/stocks/${encodeURIComponent(symbol)}/verify-financials`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`Failed to trigger financial verification for ${symbol}`);
  return res.json();
}
