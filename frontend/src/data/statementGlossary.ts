import type { GlossaryTerm } from './glossary';

export const normalizeStatementMetric = (metric: string) => metric.trim().toLowerCase().replace(/\s+/g, ' ');

export const getStatementGlossaryTerm = (metric: string): GlossaryTerm | null => {
  const normalized = normalizeStatementMetric(metric);

  if (['sales', 'revenue', 'revenue from operations', 'total income'].includes(normalized)) return 'revenue';
  if (['expenses', 'total expenses'].includes(normalized)) return 'expenses';
  if (['material cost', 'raw material cost', 'cost of materials consumed'].includes(normalized)) return 'material_cost';
  if (['employee cost', 'employee expense', 'staff cost', 'employee benefit expense'].includes(normalized)) return 'employee_cost';
  if (['other cost', 'other expenses', 'other operating expenses'].includes(normalized)) return 'other_cost';
  if (normalized === 'operating profit') return 'operating_profit';
  if (normalized === 'ebitda') return 'ebitda';
  if (normalized.includes('operating profit margin') || normalized === 'opm' || normalized === 'opm %') return 'opm';
  if (['other income', 'non-operating income'].includes(normalized)) return 'other_income';
  if (['interest', 'interest expense', 'interest expended', 'finance cost', 'finance costs'].includes(normalized)) return 'finance_cost';
  if (normalized.includes('depreciation') || normalized.includes('amortisation') || normalized.includes('amortization')) return 'depreciation';
  if (['profit before tax', 'pbt'].includes(normalized)) return 'pbt';
  if (['tax', 'tax %', 'effective tax rate'].includes(normalized)) return 'tax';
  if (['net profit', 'pat', 'profit after tax', 'net income'].includes(normalized)) return 'pat';
  if (/^(basic |diluted )?eps(?: in rs)?$/.test(normalized)) return 'eps';

  if (['equity capital', 'share capital', 'paid-up capital'].includes(normalized)) return 'equity_capital';
  if (['reserves', 'reserves and surplus'].includes(normalized)) return 'reserves';
  if (['shareholders funds', "shareholders' funds", 'shareholder funds', 'net worth', 'total equity'].includes(normalized)) return 'net_worth';
  if (['other liabilities', 'other liabilities and provisions'].includes(normalized)) return 'other_liabilities';
  if (['total liabilities', 'total liabilities and equity'].includes(normalized)) return 'total_liabilities';
  if (['borrowings', 'total borrowings', 'debt'].includes(normalized)) return 'borrowings';
  if (['fixed assets', 'net fixed assets'].includes(normalized)) return 'fixed_assets';
  if (normalized === 'net block') return 'net_block';
  if (normalized.includes('capital work in progress') || normalized === 'cwip') return 'cwip';
  if (normalized === 'investments' || normalized === 'financial investments') return 'investments';
  if (['other assets', 'other current assets', 'other non-current assets'].includes(normalized)) return 'other_assets';
  if (normalized === 'total assets') return 'total_assets';
  if (normalized.includes('receivable') || normalized.includes('debtor')) return 'receivables';
  if (normalized.includes('inventory') || normalized === 'stock in trade') return 'inventory';
  if (normalized.includes('cash equivalent') || normalized.includes('cash and bank') || normalized === 'cash' || normalized === 'cash balance') return 'cash_equivalents';

  if (normalized.includes('cash from operating') || normalized.includes('cash flow from operating') || normalized === 'operating cash flow' || normalized === 'cfo') return 'cfo';
  if (normalized.includes('cash from investing') || normalized.includes('cash flow from investing')) return 'investing_cash_flow';
  if (normalized.includes('cash from financing') || normalized.includes('cash flow from financing')) return 'financing_cash_flow';
  if (normalized.includes('net cash flow') || normalized.includes('net change in cash') || normalized.includes('net increase in cash')) return 'net_cash_flow';
  if (normalized.includes('fixed assets purchased') || normalized === 'capital expenditure' || normalized === 'capex') return 'capex';
  if (normalized.includes('dividend paid') || normalized === 'dividends' || normalized === 'equity dividend') return 'dividends';
  if (normalized.includes('debt raised') || normalized.includes('debt repaid') || normalized.includes('proceeds from borrowings') || normalized.includes('repayment of borrowings')) return 'debt_movement';
  if (normalized.includes('free cash flow') || normalized === 'fcf') return 'fcf';

  if (['deposits', 'total deposits'].includes(normalized)) return 'deposits';
  if (['advances', 'loans & advances', 'loans and advances', 'total advances'].includes(normalized)) return 'advances';
  if (['gross npa', 'gross npa %', 'gnpa', 'gnpa %'].includes(normalized)) return 'gnpa';
  if (['net npa', 'net npa %', 'nnpa', 'nnpa %'].includes(normalized)) return 'nnpa';
  if (normalized === 'nim' || normalized === 'nim %' || normalized.includes('net interest margin')) return 'nim';
  if (normalized === 'casa' || normalized === 'casa %' || normalized.includes('casa ratio')) return 'casa';
  if (normalized.includes('provision')) return 'provisions';
  if (normalized.includes('cost to income') || normalized.includes('cost-to-income')) return 'cost_to_income';
  if (normalized.includes('credit cost')) return 'credit_cost';
  if (normalized.includes('credit deposit ratio') || normalized === 'cd ratio' || normalized === 'c/d ratio') return 'cd_ratio';
  if (normalized.includes('working capital')) return 'working_capital';

  return null;
};
