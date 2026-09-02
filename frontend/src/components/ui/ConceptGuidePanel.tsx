import React, { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { BookOpen, X } from 'lucide-react';
import type { ConceptGuideContext, FinancialConceptGuide } from '../../data/glossary';
import { ConceptGuideContent } from './ConceptGuideContent';

interface ConceptGuidePanelProps extends ConceptGuideContext {
  guide: FinancialConceptGuide;
  onClose: () => void;
  onCalculationDetails?: () => void;
  returnFocusRef?: React.RefObject<HTMLElement | null>;
}

const focusableSelector = [
  'button:not([disabled])',
  '[href]',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])'
].join(',');

export const ConceptGuidePanel: React.FC<ConceptGuidePanelProps> = ({
  guide,
  onClose,
  onCalculationDetails,
  returnFocusRef,
  businessModel,
  sector,
  industry
}) => {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !panelRef.current) return;
      const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>(focusableSelector));
      if (!focusable.length) {
        event.preventDefault();
        panelRef.current.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = previousOverflow;
      const focusTarget = returnFocusRef?.current ?? previouslyFocused;
      window.setTimeout(() => focusTarget?.focus(), 0);
    };
  }, [onClose, returnFocusRef]);

  if (typeof document === 'undefined') return null;

  return createPortal(
    <div
      className="concept-guide-backdrop"
      role="presentation"
      onPointerDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        className="concept-guide-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <header className="concept-guide-header">
          <div className="flex min-w-0 items-center gap-3">
            <div className="feature-icon feature-icon-cyan"><BookOpen className="w-5 h-5" aria-hidden="true" /></div>
            <div className="min-w-0">
              <span className="help-eyebrow">Investor learning guide</span>
              <h2 id={titleId} className="concept-guide-title">{guide.title}</h2>
              {guide.shortLabel !== guide.title && <span className="concept-guide-short-label">{guide.shortLabel}</span>}
            </div>
          </div>
          <button ref={closeRef} type="button" onClick={onClose} className="icon-button" aria-label={`Close ${guide.title} guide`}>
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </header>

        <div className="concept-guide-scroll">
          <ConceptGuideContent
            guide={guide}
            businessModel={businessModel}
            sector={sector}
            industry={industry}
            onCalculationDetails={onCalculationDetails ? () => {
              onClose();
              onCalculationDetails();
            } : undefined}
          />
        </div>
      </div>
    </div>,
    document.body
  );
};
