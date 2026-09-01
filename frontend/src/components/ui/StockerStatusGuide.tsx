import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { BookOpen, Bot, Calculator, FileText, X } from 'lucide-react';
import { glossary } from '../../data/glossary';
import { STOCKER_DATA_LAYERS, STOCKER_STATUS_GUIDE } from '../../data/statusGuide';

const layerIcons = [FileText, Calculator, Bot];

export const StockerStatusGuide: React.FC = () => {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const focusTimer = window.setTimeout(() => closeRef.current?.focus(), 0);
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => {
      window.clearTimeout(focusTimer);
      window.removeEventListener('keydown', closeOnEscape);
      (previouslyFocused || triggerRef.current)?.focus();
    };
  }, [open]);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="status-guide-trigger"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls="stocker-status-guide"
        onClick={() => setOpen(true)}
      >
        <BookOpen className="w-3.5 h-3.5" aria-hidden="true" />
        Data &amp; status guide
      </button>

      {open && createPortal(
        <div
          className="status-guide-overlay"
          role="presentation"
          onPointerDown={(event) => {
            if (event.target === event.currentTarget) setOpen(false);
          }}
        >
          <section
            id="stocker-status-guide"
            className="status-guide-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="stocker-status-guide-title"
          >
            <header className="status-guide-header">
              <div>
                <h3 id="stocker-status-guide-title">How to read Stocker</h3>
                <p>Start with the number, open its help, then inspect formulas and sources when the decision warrants it.</p>
              </div>
              <button ref={closeRef} type="button" className="icon-button" onClick={() => setOpen(false)} aria-label="Close data and status guide">
                <X className="w-4 h-4" aria-hidden="true" />
              </button>
            </header>

            <div className="status-guide-body">
              <section aria-labelledby="data-layer-guide-title">
                <h4 id="data-layer-guide-title" className="status-guide-section-title">Where a result comes from</h4>
                <div className="status-guide-layer-grid">
                  {STOCKER_DATA_LAYERS.map((layer, index) => {
                    const item = glossary[layer.glossaryTerm];
                    const Icon = layerIcons[index];
                    return (
                      <article key={layer.title} className="status-guide-card">
                        <div className="status-guide-card-title"><Icon className="w-4 h-4" aria-hidden="true" />{layer.title}</div>
                        <p>{item.meaning}</p>
                        <small><strong>What to do:</strong> {item.userAction || 'Open details when you need the underlying evidence.'}</small>
                      </article>
                    );
                  })}
                </div>
              </section>

              <section aria-labelledby="status-language-guide-title">
                <h4 id="status-language-guide-title" className="status-guide-section-title">What the status means</h4>
                <div className="status-guide-status-list">
                  {STOCKER_STATUS_GUIDE.map(status => {
                    const item = glossary[status.glossaryTerm];
                    return (
                      <article key={status.label} className={`status-guide-status status-${status.glossaryTerm}`}>
                        <h5>{status.label}</h5>
                        <div>
                          <p><strong>Meaning:</strong> {item.meaning}</p>
                          <p><strong>Why shown / implication:</strong> {item.whyItMatters} {item.howStockerUses}</p>
                          <p><strong>What to do:</strong> {item.userAction || 'No action is required.'}</p>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </section>
            </div>
          </section>
        </div>,
        document.body
      )}
    </>
  );
};
