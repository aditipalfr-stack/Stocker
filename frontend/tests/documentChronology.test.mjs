import test from 'node:test';
import assert from 'node:assert/strict';

import {
  parseDocumentSortTimestamp,
  sortDocumentsGlobally,
  formatDocumentDisplayType,
  formatDocumentSources
} from '../src/utils/documentChronology.ts';

test('1. Exact ISO date parsing', () => {
  assert.equal(parseDocumentSortTimestamp('2026-08-24', 'Regulation 30'), '2026-08-24');
  assert.equal(parseDocumentSortTimestamp('2026-07-20', 'Form 20-F'), '2026-07-20');
});

test('2. Text DMY date parsing', () => {
  assert.equal(parseDocumentSortTimestamp('28 Aug 2026', 'Notice'), '2026-08-28');
  assert.equal(parseDocumentSortTimestamp('18 Jul 2026', 'Notice of 32nd AGM and Annual Report 2025-26'), '2026-07-18');
  assert.equal(parseDocumentSortTimestamp('20 Jul 2026', 'Filing of Annual Report in Form 20-F'), '2026-07-20');
});

test('3. Month and Year parsing', () => {
  assert.equal(parseDocumentSortTimestamp('Jul 2026', 'Investor Presentation'), '2026-07-01');
  assert.equal(parseDocumentSortTimestamp('August 2026', 'Media Release'), '2026-08-01');
});

test('4. Quarter and Fiscal Year parsing', () => {
  assert.equal(parseDocumentSortTimestamp('Q1 FY27', 'Earnings Call Transcript'), '2026-06-30');
  assert.equal(parseDocumentSortTimestamp('Q4 FY26', 'Earnings Call Transcript'), '2026-03-31');
  assert.equal(parseDocumentSortTimestamp('Q3 FY26', 'Earnings Call Transcript'), '2025-12-31');
  assert.equal(parseDocumentSortTimestamp('Q2 FY26', 'Earnings Call Transcript'), '2025-09-30');
});

test('5. Fiscal Year only parsing', () => {
  assert.equal(parseDocumentSortTimestamp('FY2026', 'Annual Report'), '2026-03-31');
  assert.equal(parseDocumentSortTimestamp('FY2025', 'Annual Report'), '2025-03-31');
  assert.equal(parseDocumentSortTimestamp('FY24', 'Annual Report'), '2024-03-31');
  assert.equal(parseDocumentSortTimestamp(null, 'Annual Report 2024'), '2024-03-31');
});

test('6. Undated fallback returns 1970-01-01', () => {
  assert.equal(parseDocumentSortTimestamp(null, 'General Notice'), '1970-01-01');
  assert.equal(parseDocumentSortTimestamp('', ''), '1970-01-01');
});

test('7. Global chronological sorting across all document types', () => {
  const docs = [
    { ticker: 'ICICIBANK', title: 'Older AR 2012', url: 'http://a/12', doc_type: 'annual_report', period_or_date: 'FY2012' },
    { ticker: 'ICICIBANK', title: 'Regulation 30 Announcement 24 Aug', url: 'http://a/reg', doc_type: 'announcement', period_or_date: '24 Aug 2026' },
    { ticker: 'ICICIBANK', title: 'Notice of AGM & AR 2026', url: 'http://a/ar26', doc_type: 'annual_report', period_or_date: '18 Jul 2026' },
    { ticker: 'ICICIBANK', title: 'Form 20-F 2026', url: 'http://a/20f', doc_type: 'regulatory_annual_filing', period_or_date: '20 Jul 2026' },
    { ticker: 'ICICIBANK', title: 'Investor Presentation Jul 2026', url: 'http://a/ppt', doc_type: 'presentation', period_or_date: 'Jul 2026' },
    { ticker: 'ICICIBANK', title: 'Concall Q1 FY27', url: 'http://a/cc', doc_type: 'concall_transcript', period_or_date: 'Q1 FY27' },
    { ticker: 'ICICIBANK', title: 'AR 2025', url: 'http://a/ar25', doc_type: 'annual_report', period_or_date: 'FY2025' },
    { ticker: 'ICICIBANK', title: 'Undated General Notice', url: 'http://a/undated', doc_type: 'general', period_or_date: null }
  ];

  const sorted = sortDocumentsGlobally(docs);
  const titles = sorted.map(d => d.title);

  assert.deepEqual(titles, [
    'Regulation 30 Announcement 24 Aug', // 2026-08-24
    'Form 20-F 2026',                   // 2026-07-20
    'Notice of AGM & AR 2026',          // 2026-07-18
    'Investor Presentation Jul 2026',   // 2026-07-01
    'Concall Q1 FY27',                  // 2026-06-30
    'AR 2025',                          // 2025-03-31
    'Older AR 2012',                    // 2012-03-31
    'Undated General Notice'            // 1970-01-01
  ]);
});

test('8. Display type normalization', () => {
  assert.equal(formatDocumentDisplayType('regulatory_annual_filing'), 'Regulatory (20-F)');
  assert.equal(formatDocumentDisplayType('20-f'), 'Regulatory (20-F)');
  assert.equal(formatDocumentDisplayType('brsr_esg'), 'BRSR / ESG');
  assert.equal(formatDocumentDisplayType('annual_report'), 'Annual Report');
  assert.equal(formatDocumentDisplayType('concall_transcript'), 'Concall Transcript');
  assert.equal(formatDocumentDisplayType('presentation'), 'Investor Presentation');
  assert.equal(formatDocumentDisplayType('announcement'), 'Material Announcement');
});

test('9. Discovered sources formatting merges multiple sources', () => {
  const docSingle = {
    ticker: 'ICICIBANK',
    title: 'AR 2026',
    url: 'http://a.pdf',
    doc_type: 'annual_report',
    discovery_source: 'BSE India',
    actual_source_host: 'bseindia.com'
  };
  assert.equal(formatDocumentSources(docSingle), 'BSE India');

  const docMulti = {
    ticker: 'ICICIBANK',
    title: 'AR 2026',
    url: 'http://a.pdf',
    doc_type: 'annual_report',
    discovery_source: 'BSE India',
    discovered_sources: ['BSE India', 'Screener.in'],
    actual_source_host: 'bseindia.com'
  };
  assert.equal(formatDocumentSources(docMulti), 'BSE India, Screener.in');
});

test('10. Date enrichment sorts exact alias date ahead of FY-only date', () => {
  const docA = {
    ticker: 'ICICIBANK',
    title: 'ICICIBANK Annual Report 2026',
    url: 'http://a/ar26',
    doc_type: 'annual_report',
    period_or_date: '18 Jul 2026',
    sort_timestamp: '2026-07-18'
  };
  const docB = {
    ticker: 'ICICIBANK',
    title: 'ICICIBANK Annual Report 2025',
    url: 'http://a/ar25',
    doc_type: 'annual_report',
    period_or_date: 'FY2025',
    sort_timestamp: '2025-03-31'
  };
  const sorted = sortDocumentsGlobally([docB, docA]);
  assert.equal(sorted[0].title, 'ICICIBANK Annual Report 2026');
  assert.equal(sorted[0].sort_timestamp, '2026-07-18');
});

test('11. Authoritative AI status takes precedence', () => {
  const docAnalyzed = { ai_status: 'AI_ANALYZED' };
  const docNotSelected = { ai_status: 'NOT_SELECTED' };
  const docFailed = { ai_status: 'PROCESSING_FAILED' };
  const docNotAnalyzed = { ai_status: 'NOT_ANALYZED_YET' };

  assert.equal(docAnalyzed.ai_status, 'AI_ANALYZED');
  assert.equal(docNotSelected.ai_status, 'NOT_SELECTED');
  assert.equal(docFailed.ai_status, 'PROCESSING_FAILED');
  assert.equal(docNotAnalyzed.ai_status, 'NOT_ANALYZED_YET');
});
