import { DocumentItem } from '../types';

const MONTH_MAP: Record<string, number> = {
  jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6,
  jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12
};

export function parseDocumentSortTimestamp(periodOrDate?: string | null, title?: string): string {
  const combined = `${periodOrDate || ''} ${title || ''}`.trim();
  if (!combined) {
    return '1970-01-01';
  }

  // 1. Exact ISO date: YYYY-MM-DD
  const mIso = combined.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (mIso) {
    return `${mIso[1]}-${mIso[2]}-${mIso[3]}`;
  }

  // 2. Exact text date: '28 Aug 2026', '28-Aug-2026', '21 August 2026'
  const mDmy = combined.match(/(\d{1,2})[-/ ]+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/ ,]+(\d{4})/i);
  if (mDmy) {
    const day = parseInt(mDmy[1], 10);
    const monStr = mDmy[2].slice(0, 3).toLowerCase();
    const mon = MONTH_MAP[monStr] || 1;
    const yr = parseInt(mDmy[3], 10);
    return `${yr}-${String(mon).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  }

  const mMdy = combined.match(/(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/ ]+(\d{1,2})[-/ ,]+(\d{4})/i);
  if (mMdy) {
    const monStr = mMdy[1].slice(0, 3).toLowerCase();
    const mon = MONTH_MAP[monStr] || 1;
    const day = parseInt(mMdy[2], 10);
    const yr = parseInt(mMdy[3], 10);
    return `${yr}-${String(mon).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  }

  // 3. Month & Year only: 'Jul 2026', 'July 2026'
  const mMy = combined.match(/(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/ ]+(\d{4})/i);
  if (mMy) {
    const monStr = mMy[1].slice(0, 3).toLowerCase();
    const mon = MONTH_MAP[monStr] || 1;
    const yr = parseInt(mMy[2], 10);
    return `${yr}-${String(mon).padStart(2, '0')}-01`;
  }

  // 4. Quarter & Fiscal Year: 'Q1 FY27', 'Q4 FY26', 'Q1 FY2026'
  const mQ = combined.match(/Q([1-4])\s*(?:FY)?\s*(\d{2,4})/i);
  if (mQ) {
    const qNum = parseInt(mQ[1], 10);
    const rawYr = parseInt(mQ[2], 10);
    const fyYr = rawYr > 1000 ? rawYr : 2000 + rawYr;
    if (qNum === 1) return `${fyYr - 1}-06-30`;
    if (qNum === 2) return `${fyYr - 1}-09-30`;
    if (qNum === 3) return `${fyYr - 1}-12-31`;
    if (qNum === 4) return `${fyYr}-03-31`;
  }

  // 5. Fiscal Year only: 'FY2026', 'FY26', '2025-26'
  const mFy = combined.match(/FY\s*(\d{2,4})/i);
  if (mFy) {
    const rawYr = parseInt(mFy[1], 10);
    const fyYr = rawYr > 1000 ? rawYr : 2000 + rawYr;
    return `${fyYr}-03-31`;
  }

  const mFyRange = combined.match(/(\d{4})\s*[-–]\s*(\d{2,4})/);
  if (mFyRange) {
    const yr1 = parseInt(mFyRange[1], 10);
    const yr2 = parseInt(mFyRange[2], 10);
    const fyYr = yr2 > 1000 ? yr2 : parseInt(String(yr1).slice(0, 2) + String(yr2).padStart(2, '0'), 10);
    return `${fyYr}-03-31`;
  }

  // 6. Year in title: 'Annual Report 2024'
  const mYr = combined.match(/\b(20\d{2})\b/);
  if (mYr) {
    return `${mYr[1]}-03-31`;
  }

  return '1970-01-01';
}

export function sortDocumentsGlobally(docs: DocumentItem[]): DocumentItem[] {
  return [...docs].sort((a, b) => {
    const tsA = a.sort_timestamp || parseDocumentSortTimestamp(a.period_or_date, a.title);
    const tsB = b.sort_timestamp || parseDocumentSortTimestamp(b.period_or_date, b.title);
    if (tsA !== tsB) {
      return tsB.localeCompare(tsA);
    }
    return (a.title || '').localeCompare(b.title || '');
  });
}

export function formatDocumentDisplayType(docType?: string): string {
  if (!docType) return 'Filing';
  const t = docType.toLowerCase();
  if (t === 'regulatory_annual_filing' || t.includes('20-f')) return 'Regulatory (20-F)';
  if (t === 'brsr_esg' || t.includes('brsr') || t.includes('esg')) return 'BRSR / ESG';
  if (t === 'annual_report' || t.includes('annual')) return 'Annual Report';
  if (t === 'concall_transcript' || t.includes('concall')) return 'Concall Transcript';
  if (t === 'presentation' || t.includes('presentation')) return 'Investor Presentation';
  if (t === 'announcement' || t.includes('announcement')) return 'Material Announcement';
  return 'Filing';
}

export function formatDocumentSources(doc: DocumentItem): string {
  const sources = new Set<string>();
  if (doc.discovery_source) sources.add(doc.discovery_source);
  if (doc.discovered_sources) {
    for (const s of doc.discovered_sources) {
      if (s) sources.add(s);
    }
  }
  if (sources.size === 0) return doc.actual_source_host || 'Discovered source';
  return Array.from(sources).join(', ');
}
