import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Calculator, HelpCircle, X } from 'lucide-react';
import { glossary, GlossaryTerm } from '../../data/glossary';

interface ConceptHelpProps {
  term: GlossaryTerm;
  label?: string;
  className?: string;
  businessModel?: string;
  onCalculationDetails?: () => void;
}

export const ConceptHelp: React.FC<ConceptHelpProps> = ({
  term,
  label,
  className = '',
  businessModel,
  onCalculationDetails
}) => {
  const item = glossary[term];
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeTimer = useRef<number | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const isFinancialBusiness = ['BANK', 'NBFC_LENDER', 'INSURANCE', 'OTHER_FINANCIAL'].includes(businessModel || '');

  const cancelClose = () => {
    if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
  };

  const open = () => {
    cancelClose();
    const rect = triggerRef.current?.getBoundingClientRect();
    if (rect) {
      const popoverWidth = 320;
      setPosition({
        top: rect.bottom + 8,
        left: Math.max(12, Math.min(rect.left + rect.width / 2 - popoverWidth / 2, window.innerWidth - popoverWidth - 12))
      });
    }
    setIsOpen(true);
  };

  const scheduleClose = () => {
    closeTimer.current = window.setTimeout(() => setIsOpen(false), 140);
  };

  useEffect(() => {
    if (!isOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => event.key === 'Escape' && setIsOpen(false);
    const closeOnOutsidePress = (event: PointerEvent) => {
      const target = event.target as Element;
      if (!triggerRef.current?.contains(target) && !target.closest('[data-concept-popover]')) setIsOpen(false);
    };
    const closeOnResize = () => setIsOpen(false);
    window.addEventListener('keydown', closeOnEscape);
    window.addEventListener('pointerdown', closeOnOutsidePress);
    window.addEventListener('resize', closeOnResize);
    window.addEventListener('scroll', closeOnResize, true);
    return () => {
      window.removeEventListener('keydown', closeOnEscape);
      window.removeEventListener('pointerdown', closeOnOutsidePress);
      window.removeEventListener('resize', closeOnResize);
      window.removeEventListener('scroll', closeOnResize, true);
    };
  }, [isOpen]);

  useEffect(() => () => cancelClose(), []);

  return (
    <span className={`concept-help ${className}`}>
      {label && <span>{label}</span>}
      <button
        ref={triggerRef}
        type="button"
        className="concept-help-trigger"
        aria-label={`Learn about ${item.title}`}
        aria-expanded={isOpen}
        onMouseEnter={open}
        onMouseLeave={scheduleClose}
        onFocus={open}
        onBlur={scheduleClose}
        onClick={(event) => {
          event.stopPropagation();
          isOpen ? setIsOpen(false) : open();
        }}
      >
        <HelpCircle className="w-3.5 h-3.5" aria-hidden="true" />
      </button>

      {isOpen && createPortal(
        <div
          className="concept-popover"
          data-concept-popover
          role="dialog"
          aria-label={`${item.title} definition`}
          style={{ top: position.top, left: position.left }}
          onMouseEnter={cancelClose}
          onMouseLeave={scheduleClose}
          onFocus={cancelClose}
          onBlur={scheduleClose}
          onClick={(event) => event.stopPropagation()}
        >
          <div className="flex items-start justify-between gap-3">
            <h4 className="text-sm font-bold text-primary">{item.title}</h4>
            <button type="button" onClick={() => setIsOpen(false)} className="icon-button -mt-1 -mr-1" aria-label="Close help">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <p className="text-xs leading-relaxed text-secondary">{item.meaning}</p>
          <div>
            <span className="help-eyebrow">Why it matters</span>
            <p className="text-xs leading-relaxed text-secondary">{item.whyItMatters}</p>
          </div>
          {item.howStockerUses && (
            <div>
              <span className="help-eyebrow">How Stocker uses it</span>
              <p className="text-xs leading-relaxed text-secondary">{item.howStockerUses}</p>
            </div>
          )}
          {isFinancialBusiness && item.financialBusinessNote && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-2">
              <span className="help-eyebrow">For this financial business</span>
              <p className="text-xs leading-relaxed text-secondary">{item.financialBusinessNote}</p>
            </div>
          )}
          {item.formula && (
            <div>
              <span className="help-eyebrow">General formula</span>
              <code className="formula-chip">{item.formula}</code>
            </div>
          )}
          {onCalculationDetails && (
            <button
              type="button"
              className="calculation-link"
              onClick={() => {
                setIsOpen(false);
                onCalculationDetails();
              }}
            >
              <Calculator className="w-3.5 h-3.5" />
              View this stock’s actual calculation
            </button>
          )}
        </div>,
        document.body
      )}
    </span>
  );
};
