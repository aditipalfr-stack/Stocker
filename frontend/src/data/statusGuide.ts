import type { GlossaryTerm } from './glossary';

export interface StockerDataLayerGuide {
  title: string;
  glossaryTerm: GlossaryTerm;
  glanceLabel: string;
}

export interface StockerStatusGuideEntry {
  label: string;
  glossaryTerm: GlossaryTerm;
}

export const STOCKER_DATA_LAYERS: StockerDataLayerGuide[] = [
  { title: 'Reported financial data', glossaryTerm: 'standardized', glanceLabel: 'Reported data' },
  { title: 'Stocker calculation', glossaryTerm: 'stocker_calculation', glanceLabel: 'Stocker calculation' },
  { title: 'AI interpretation', glossaryTerm: 'ai_interpretation', glanceLabel: 'AI interpretation' }
];

export const STOCKER_STATUS_GUIDE: StockerStatusGuideEntry[] = [
  { label: 'Verified', glossaryTerm: 'verified' },
  { label: 'Standardized', glossaryTerm: 'standardized' },
  { label: 'Mixed', glossaryTerm: 'mixed' },
  { label: 'Discrepancy', glossaryTerm: 'discrepancy' },
  { label: 'Provisional', glossaryTerm: 'provisional' },
  { label: 'Evidence-enriched', glossaryTerm: 'evidence_enriched' },
  { label: 'Stale', glossaryTerm: 'stale' },
  { label: 'Unavailable / Insufficient evidence', glossaryTerm: 'unavailable' },
  { label: 'Not run / Not searched', glossaryTerm: 'not_run' }
];

export type ProvenanceStatusKind = 'standardized' | 'verified' | 'mixed' | 'discrepancy' | 'unavailable';

export interface ProvenanceStatusPresentation {
  label: string;
  glossaryTerm: GlossaryTerm;
  emphasis: 'low' | 'medium' | 'high';
}

export const PROVENANCE_STATUS_PRESENTATION: Record<ProvenanceStatusKind, ProvenanceStatusPresentation> = {
  standardized: { label: 'Standardized', glossaryTerm: 'standardized', emphasis: 'low' },
  verified: { label: 'Verified', glossaryTerm: 'verified', emphasis: 'medium' },
  mixed: { label: 'Mixed', glossaryTerm: 'mixed', emphasis: 'medium' },
  discrepancy: { label: 'Discrepancy', glossaryTerm: 'discrepancy', emphasis: 'high' },
  unavailable: { label: 'Unavailable', glossaryTerm: 'unavailable', emphasis: 'medium' }
};

export const resolveProvenanceStatusKind = (quality: string, hasDiscrepancy?: boolean): ProvenanceStatusKind => {
  if (quality === 'discrepant' || hasDiscrepancy) return 'discrepancy';
  if (quality === 'verified') return 'verified';
  if (quality === 'mixed') return 'mixed';
  if (quality === 'insufficient') return 'unavailable';
  return 'standardized';
};
