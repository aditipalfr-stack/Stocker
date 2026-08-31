import React, { useState } from 'react';
import { Check, PlusCircle, RefreshCw, Search } from 'lucide-react';
import { searchCompanies } from '../api';
import type { CompanySearchResult } from '../types';

interface CompanySearchAddProps {
  disabled?: boolean;
  onAdd: (query: string) => Promise<void>;
  onOpenExisting: (symbol: string) => Promise<void>;
}

const normalized = (value: string) => value.toLowerCase().replace(/[^a-z0-9]/g, '');

export const CompanySearchAdd: React.FC<CompanySearchAddProps> = ({ disabled, onAdd, onOpenExisting }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<CompanySearchResult[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [phase, setPhase] = useState<'idle' | 'resolving' | 'adding'>('idle');
  const [error, setError] = useState<string | null>(null);

  const chooseCompany = async (company: CompanySearchResult) => {
    setError(null);
    setResults([]);
    try {
      if (company.already_added) {
        setPhase('resolving');
        await onOpenExisting(company.symbol);
      } else {
        setPhase('adding');
        await onAdd(company.symbol);
      }
      setQuery('');
    } catch (err: any) {
      setError(err.message || `Could not add ${company.company_name}`);
    } finally {
      setPhase('idle');
    }
  };

  const resolveQuery = async () => {
    const rawQuery = query.trim();
    if (!rawQuery || phase !== 'idle') return;
    setPhase('resolving');
    setError(null);
    setResults([]);
    try {
      const response = await searchCompanies(rawQuery);
      if (response.results.length === 0) {
        setError('No matching listed company found. Try a ticker, company name, or alias.');
        return;
      }

      const exact = response.results.find(result =>
        normalized(result.symbol) === normalized(rawQuery) ||
        normalized(result.company_name) === normalized(rawQuery)
      );
      const clearMatch = exact || (response.results.length === 1 ? response.results[0] : null);
      if (clearMatch) {
        setPhase('idle');
        await chooseCompany(clearMatch);
        return;
      }

      setResults(response.results);
      setActiveIndex(0);
    } catch (err: any) {
      setError(err.message || 'Company search failed.');
    } finally {
      setPhase(current => current === 'resolving' ? 'idle' : current);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (results.length > 0) {
      await chooseCompany(results[activeIndex]);
      return;
    }
    await resolveQuery();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (results.length === 0) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex(index => (index + 1) % results.length);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex(index => (index - 1 + results.length) % results.length);
    } else if (event.key === 'Escape') {
      setResults([]);
    }
  };

  const busy = phase !== 'idle';

  return (
    <form onSubmit={handleSubmit} className="flex items-center w-full md:w-auto relative" role="search">
      <div className="relative w-full md:w-96">
        <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
        <label htmlFor="company-search-add" className="sr-only">Search for a company to add</label>
        <input
          id="company-search-add"
          type="text"
          autoComplete="off"
          placeholder="Ticker, company name, or alias..."
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setResults([]);
            setError(null);
          }}
          onKeyDown={handleKeyDown}
          aria-expanded={results.length > 0}
          aria-controls="company-search-results"
          aria-activedescendant={results.length > 0 ? `company-result-${activeIndex}` : undefined}
          className="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl pl-9 pr-24 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all"
        />
        <button
          type="submit"
          disabled={busy || disabled || !query.trim()}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold px-2.5 py-1 rounded-lg transition-colors flex items-center gap-1 shadow-sm"
        >
          {busy ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <PlusCircle className="w-3.5 h-3.5" />}
          <span>{phase === 'resolving' ? 'Resolving' : phase === 'adding' ? 'Adding' : results.length > 0 ? 'Add' : 'Find'}</span>
        </button>

        {results.length > 0 && (
          <div id="company-search-results" role="listbox" className="absolute top-full mt-2 left-0 right-0 z-[60] rounded-2xl border border-slate-700 bg-slate-950 shadow-2xl overflow-hidden p-1.5">
            <p className="px-3 py-2 text-[10px] uppercase tracking-wider text-slate-500 font-bold">Choose the matching company</p>
            {results.map((result, index) => (
              <button
                id={`company-result-${index}`}
                key={`${result.symbol}-${result.exchange || ''}`}
                type="button"
                role="option"
                aria-selected={index === activeIndex}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => chooseCompany(result)}
                className={`w-full px-3 py-2.5 rounded-xl text-left flex items-center justify-between gap-3 ${index === activeIndex ? 'bg-slate-800' : 'hover:bg-slate-900'}`}
              >
                <span className="min-w-0">
                  <span className="block text-xs font-bold text-slate-100 truncate">{result.company_name}</span>
                  <span className="block text-[11px] text-slate-400 font-mono">{result.symbol}{result.exchange ? ` • ${result.exchange}` : ''}</span>
                </span>
                {result.already_added ? (
                  <span className="shrink-0 text-[10px] text-cyan-300 flex items-center gap-1"><Check className="w-3 h-3" /> Added</span>
                ) : (
                  <span className="shrink-0 text-[10px] text-emerald-300">Add company</span>
                )}
              </button>
            ))}
          </div>
        )}

        {error && (
          <div role="alert" className="absolute top-full mt-2 left-0 right-0 z-[60] rounded-xl border border-rose-800 bg-rose-950 px-3 py-2 text-[11px] text-rose-200 shadow-xl">
            {error}
          </div>
        )}
      </div>
    </form>
  );
};
