import { StockSummary, StockDetail, ProjectionAssumption, ProjectionResult, ComparisonItem } from './types';

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

