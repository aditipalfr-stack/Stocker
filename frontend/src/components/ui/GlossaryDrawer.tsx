import React, { useEffect, useMemo, useRef, useState } from 'react';
import { BookOpen, Search, X } from 'lucide-react';
import { glossaryEntries } from '../../data/glossary';

interface GlossaryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export const GlossaryDrawer: React.FC<GlossaryDrawerProps> = ({ isOpen, onClose }) => {
  const [query, setQuery] = useState('');
  const searchRef = useRef<HTMLInputElement>(null);

  const results = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return glossaryEntries;
    return glossaryEntries.filter(([, item]) =>
      [item.title, item.meaning, item.whyItMatters, ...(item.aliases || [])]
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
    const closeOnEscape = (event: KeyboardEvent) => event.key === 'Escape' && onClose();
    window.addEventListener('keydown', closeOnEscape);
    return () => {
      window.clearTimeout(focusTimer);
      window.removeEventListener('keydown', closeOnEscape);
      document.body.style.overflow = previousOverflow;
    };
  }, [isOpen, onClose]);

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
            <div className="feature-icon"><BookOpen className="w-5 h-5" /></div>
            <div>
              <h2 id="glossary-title" className="text-lg font-bold text-primary">Investor Glossary</h2>
              <p className="text-xs text-secondary">Simple explanations, without the jargon.</p>
            </div>
          </div>
          <button type="button" onClick={onClose} className="icon-button" aria-label="Close glossary">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-5 py-4 border-b border-theme">
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
        </div>

        <div className="glossary-list">
          {results.length ? results.map(([key, item]) => (
            <article key={key} className="glossary-entry">
              <h3 className="text-sm font-bold text-primary">{item.title}</h3>
              <p className="text-xs leading-relaxed text-secondary">{item.meaning}</p>
              <div>
                <span className="help-eyebrow">Why it matters</span>
                <p className="text-xs leading-relaxed text-secondary">{item.whyItMatters}</p>
              </div>
              {item.formula && <code className="formula-chip">{item.formula}</code>}
            </article>
          )) : (
            <div className="py-16 text-center text-sm text-muted">No glossary terms match “{query}”.</div>
          )}
        </div>
      </aside>
    </div>
  );
};
