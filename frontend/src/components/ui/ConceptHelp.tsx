import React, { useRef, useState } from 'react';
import { HelpCircle } from 'lucide-react';
import type { GlossaryTerm } from '../../data/glossary';
import { getFinancialConceptGuide } from '../../data/glossary';
import { ConceptGuidePanel } from './ConceptGuidePanel';

interface ConceptHelpProps {
  term: GlossaryTerm | string;
  label?: string;
  className?: string;
  businessModel?: string;
  sector?: string;
  industry?: string;
  onCalculationDetails?: () => void;
}

export const ConceptHelp: React.FC<ConceptHelpProps> = ({
  term,
  label,
  className = '',
  businessModel,
  sector,
  industry,
  onCalculationDetails
}) => {
  const guide = getFinancialConceptGuide(term);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [isOpen, setIsOpen] = useState(false);

  if (!guide) return label ? <span className={className}>{label}</span> : null;

  return (
    <span className={`concept-help ${className}`}>
      <button
        ref={triggerRef}
        type="button"
        className={`concept-help-trigger ${label ? 'concept-help-labelled' : ''}`}
        aria-label={label ? `${label}: open beginner guide` : `Learn about ${guide.title}`}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        onClick={(event) => {
          event.stopPropagation();
          setIsOpen(true);
        }}
      >
        {label && <span>{label}</span>}
        <HelpCircle className="w-3.5 h-3.5" aria-hidden="true" />
      </button>

      {isOpen && (
        <ConceptGuidePanel
          guide={guide}
          businessModel={businessModel}
          sector={sector}
          industry={industry}
          onClose={() => setIsOpen(false)}
          onCalculationDetails={onCalculationDetails}
          returnFocusRef={triggerRef}
        />
      )}
    </span>
  );
};
