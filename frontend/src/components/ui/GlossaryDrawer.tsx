import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, BookOpen, ChevronRight, Search, X } from 'lucide-react';
import { glossary, glossaryEntries, GlossaryTerm } from '../../data/glossary';
import { ConceptGuideContent } from './ConceptGuideContent';

interface GlossaryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export const GlossaryDrawer: React.FC<GlossaryDrawerProps> = ({ isOpen, onClose }) => {
  const [query, setQuery] = useState('');
  const [selectedTerm, setSelectedTerm] = useState<GlossaryTerm | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  const results = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return glossaryEntries;
    return glossaryEntries.filter(([, item]) =>
      [item.title, item.shortLabel, item.plainEnglish, item.whyItMatters, item.stockerUsage, ...(item.aliases || [])]
        .join(' ')
        .toLowerCase()
        .includes(normalized)
    );
  }, [query]);

  useEffect(() => {
    if (!isOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusTimer = window.setTimeout(() => searchRef.current?.focus(), 60);
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      if (selectedTerm) setSelectedTerm(null);
      else onClose();
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => {
      window.clearTimeout(focusTimer);
      window.removeEventListener('keydown', closeOnEscape);
      document.body.style.overflow = previousOverflow;
    };
  }, [isOpen, onClose, selectedTerm]);

  useEffect(() => {
    if (isOpen) {
      previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    } else if (previousFocusRef.current) {
      const target = previousFocusRef.current;
      window.setTimeout(() => target.focus(), 0);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <aside
        className="glossary-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="glossary-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="glossary-header">
          <div className="flex items-center gap-3">
            {selectedTerm && (
              <button type="button" onClick={() => setSelectedTerm(null)} className="icon-button" aria-label="Back to glossary list">
                <ArrowLeft className="w-5 h-5" />
              </button>
            )}
            <div className="feature-icon"><BookOpen className="w-5 h-5" /></div>
            <div>
              <h2 id="glossary-title" className="text-lg font-bold text-primary">{selectedTerm ? glossary[selectedTerm].title : 'Investor Learning Guide'}</h2>
              <p className="text-xs text-secondary">{selectedTerm ? 'Practical context for beginner investors.' : 'Search a term, then open its concise learning guide.'}</p>
            </div>
          </div>
          <button type="button" onClick={onClose} className="icon-button" aria-label="Close glossary">
            <X className="w-5 h-5" />
          </button>
        </div>

        {!selectedTerm && <div className="px-5 py-4 border-b border-theme">
          <div className="relative">
            <Search className="w-4 h-4 text-muted absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              ref={searchRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search FCF, WACC, guidance…"
              className="theme-input w-full pl-9 pr-3 py-2.5 text-sm"
            />
          </div>
        </div>}

        <div className="glossary-list">
          {selectedTerm ? (
            <ConceptGuideContent guide={glossary[selectedTerm]} />
          ) : results.length ? results.map(([key, item]) => (
            <button key={key} type="button" className="glossary-entry glossary-entry-button" onClick={() => setSelectedTerm(key)}>
              <span className="flex items-center justify-between gap-3">
                <span className="text-sm font-bold text-primary">{item.title}</span>
                <ChevronRight className="w-4 h-4 text-muted" aria-hidden="true" />
              </span>
              <span className="text-xs leading-relaxed text-secondary">{item.plainEnglish}</span>
            </button>
          )) : (
            <div className="py-16 text-center text-sm text-muted">No glossary terms match “{query}”.</div>
          )}
        </div>
      </aside>
    </div>
  );
};
