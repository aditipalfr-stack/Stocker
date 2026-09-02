import React from 'react';
import { Calculator, Lightbulb, TriangleAlert } from 'lucide-react';
import type { ConceptGuideContext, FinancialConceptGuide } from '../../data/glossary';
import { getRelevantSectorNotes } from '../../data/glossary';

interface ConceptGuideContentProps extends ConceptGuideContext {
  guide: FinancialConceptGuide;
  onCalculationDetails?: () => void;
}

export const ConceptGuideContent: React.FC<ConceptGuideContentProps> = ({
  guide,
  businessModel,
  sector,
  industry,
  onCalculationDetails
}) => {
  const sectorNotes = getRelevantSectorNotes(guide, { businessModel, sector, industry });

  return (
    <div className="concept-guide-content">
      <section className="concept-guide-hero" aria-labelledby={`concept-${guide.term}-plain-language`}>
        <span className="help-eyebrow">In plain English</span>
        <p id={`concept-${guide.term}-plain-language`} className="concept-guide-plain">{guide.plainEnglish}</p>
      </section>

      {guide.formula && (
        <section className="concept-guide-block">
          <span className="help-eyebrow">Formula</span>
          <code className="formula-chip concept-guide-formula">{guide.formula}</code>
          {guide.formulaInputs?.length ? (
            <div className="formula-input-grid" aria-label="Formula inputs">
              {guide.formulaInputs.map(input => (
                <div key={input.label} className="formula-input-item">
                  <strong>{input.label}</strong>
                  <span>{input.meaning}</span>
                </div>
              ))}
            </div>
          ) : null}
        </section>
      )}

      <div className="concept-guide-grid">
        <section className="concept-guide-block">
          <span className="help-eyebrow">Why this matters</span>
          <p>{guide.whyItMatters}</p>
        </section>

        <section className="concept-guide-block">
          <span className="help-eyebrow">How to read it</span>
          <ul className="concept-guide-list">
            {guide.interpretation.map(item => <li key={item}>{item}</li>)}
          </ul>
        </section>
      </div>

      {guide.practicalExample && (
        <section className="concept-guide-example">
          <div className="concept-guide-section-title"><Lightbulb className="w-4 h-4" aria-hidden="true" /> Practical example</div>
          <div className="example-inputs">
            {guide.practicalExample.inputs.map(input => <span key={input}>{input}</span>)}
          </div>
          <code>{guide.practicalExample.calculation}</code>
          <p>{guide.practicalExample.takeaway}</p>
        </section>
      )}

      {guide.commonMistake && (
        <section className="concept-guide-warning">
          <div className="concept-guide-section-title"><TriangleAlert className="w-4 h-4" aria-hidden="true" /> Common beginner mistake</div>
          <p>{guide.commonMistake}</p>
        </section>
      )}

      {sectorNotes.length > 0 && (
        <section className="concept-guide-block">
          <span className="help-eyebrow">Sector note</span>
          <div className="sector-note-list">
            {sectorNotes.map(note => (
              <div key={`${note.context}-${note.note}`} className="sector-note">
                <strong>{note.context}</strong>
                <p>{note.note}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="concept-guide-stocker">
        <span className="help-eyebrow">How Stocker uses it</span>
        <p>{guide.stockerUsage}</p>
      </section>

      {guide.userAction && (
        <section className="concept-guide-block">
          <span className="help-eyebrow">What you need to do</span>
          <p>{guide.userAction}</p>
        </section>
      )}

      {onCalculationDetails && (
        <button type="button" className="calculation-link" onClick={onCalculationDetails}>
          <Calculator className="w-4 h-4" aria-hidden="true" />
          View this stock’s actual formula and inputs
        </button>
      )}
    </div>
  );
};
