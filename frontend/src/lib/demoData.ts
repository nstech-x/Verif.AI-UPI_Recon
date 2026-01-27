/**
 * Centralized Demo Data Generator
 * This ensures all dashboards show consistent, realistic reconciliation data
 * in DEMO MODE without requiring backend computation
 */

export interface DemoSummaryData {
  run_id: string;
  generated_at: string;
  status: string;
  totals: { count: number; amount: number };
  matched: { count: number; amount: number };
  unmatched: { count: number; amount: number };
  partial_matches: { count: number; amount: number };
  hanging: { count: number; amount: number };
  exceptions: { count: number; amount: number };
  inflow_outflow: {
    inward: { count: number; amount: number };
    outward: { count: number; amount: number };
  };
  total_transactions?: number;
  breakdown?: any;
  summary?: any;
  disputes?: {
    total: number;
    open: number;
    working: number;
    closed: number;
    byCategory: Record<string, number>;
    tatBreached: number;
  };
  validation?: {
    totalValidated: number;
    passed: number;
    failed: number;
    warnings: number;
    criticalErrors: number;
    byType: Record<string, number>;
    total?: number;
  };
}

export interface DemoHistoricalData {
  month: string;
  allTxns: number;
  reconciled: number;
  breaks: number;
  matchRate: number;
  inward?: number;
  outward?: number;
}

/**
 * Generate consistent demo summary data
 * Total: 12,500 transactions
 * Matched: 91% (11,375)
 * Partial: 4% (500)
 * Hanging: 3% (375)
 * Unmatched: 2% (250)
 */
export const generateDemoSummary = (): DemoSummaryData => {
  const now = new Date();
  const runId = `RUN_DEMO_${now.toISOString().split('T')[0].replace(/-/g, '')}`;
  
  const totalCount = 12500;
  const matchedCount = 11375; // 91%
  const partialCount = 500; // 4%
  const hangingCount = 375; // 3%
  const unmatchedCount = 250; // 2%
  
  // Total breaks = partial + hanging + unmatched
  const totalBreaks = partialCount + hangingCount + unmatchedCount;
  
  return {
    run_id: runId,
    generated_at: now.toISOString(),
    status: 'completed',
    total_transactions: totalCount,
    totals: {
      count: totalCount,
      amount: 458923671.50
    },
    matched: {
      count: matchedCount,
      amount: 417456234.25
    },
    partial_matches: {
      count: partialCount,
      amount: 18345678.50
    },
    hanging: {
      count: hangingCount,
      amount: 13876543.25
    },
    unmatched: {
      count: unmatchedCount,
      amount: 9245215.50
    },
    exceptions: {
      count: totalBreaks,
      amount: 41467437.25
    },
    inflow_outflow: {
      inward: {
        count: 7125,
        amount: 267845123.75
      },
      outward: {
        count: 5375,
        amount: 191078547.75
      }
    },
    breakdown: {
      matched: { count: matchedCount, amount: 417456234.25 },
      partial_matches: { count: partialCount, amount: 18345678.50 },
      hanging: { count: hangingCount, amount: 13876543.25 },
      unmatched: { count: unmatchedCount, amount: 9245215.50 }
    },
    summary: {
      matched: { count: matchedCount, amount: 417456234.25 },
      partial_matches: { count: partialCount, amount: 18345678.50 },
      hanging: { count: hangingCount, amount: 13876543.25 },
      unmatched: { count: unmatchedCount, amount: 9245215.50 }
    },
    disputes: {
      total: 50,
      open: 18,
      working: 15,
      closed: 17,
      byCategory: {
        "Chargeback": 22,
        "Fraud": 15,
        "Credit Adjustment": 13
      },
      tatBreached: 5
    },
    validation: {
      totalValidated: totalCount,
      passed: Math.floor(totalCount * 0.97),
      failed: Math.floor(totalCount * 0.03),
      warnings: Math.floor(totalCount * 0.05),
      criticalErrors: Math.floor(totalCount * 0.008),
      byType: {
        "Format Validation": Math.floor(totalCount * 0.98),
        "Amount Validation": Math.floor(totalCount * 0.96),
        "Date Validation": Math.floor(totalCount * 0.99),
        "Duplicate Check": Math.floor(totalCount * 0.95)
      }
    }
  };
};

/**
 * Generate historical data for charts
 * Shows realistic trend over 12 months
 */
export const generateDemoHistorical = (): DemoHistoricalData[] => {
  const months = [
    '2024-01', '2024-02', '2024-03', '2024-04', '2024-05', '2024-06',
    '2024-07', '2024-08', '2024-09', '2024-10', '2024-11', '2024-12'
  ];
  
  return months.map((month, index) => {
    const baseTotal = 11000 + (index * 200); // Growing trend
    const matchRate = 88 + Math.random() * 5; // 88-93% match rate
    const reconciled = Math.floor(baseTotal * (matchRate / 100));
    const breaks = baseTotal - reconciled;
    
    // Split into inward/outward (roughly 60/40)
    const inward = Math.floor(baseTotal * (0.57 + Math.random() * 0.06)); // 57-63%
    const outward = baseTotal - inward;
    
    return {
      month,
      allTxns: baseTotal,
      reconciled,
      breaks,
      matchRate: Math.round(matchRate * 10) / 10,
      inward,
      outward
    };
  });
};

/**
 * Generate demo hanging transactions
 * These appear in Unmatched Dashboard and Force Match
 */
export const generateDemoHangingTransactions = () => {
  const hanging: any[] = [];
  const sources = ['NPCI', 'CBS', 'SWITCH'];
  const today = new Date();
  
  for (let i = 0; i < 375; i++) {
    const source = sources[i % 3];
    const amount = 500 + Math.random() * 9500;
    // Generate dates in the last 30 days
    const daysAgo = i % 30;
    const date = new Date(today);
    date.setDate(date.getDate() - daysAgo);
    
    hanging.push({
      source,
      rrn: `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}${String(date.getDate()).padStart(2, '0')}${String(100000 + i).slice(-6)}`,
      upiTransactionId: `UPI${String(10000000 + i).slice(-8)}`,
      drCr: i % 2 === 0 ? 'Cr' : 'Dr',
      amount,
      amountFormatted: `₹${amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      tranDate: date.toLocaleDateString('en-GB'),
      time: `${String(Math.floor(Math.random() * 24)).padStart(2, '0')}:${String(Math.floor(Math.random() * 60)).padStart(2, '0')}:${String(Math.floor(Math.random() * 60)).padStart(2, '0')}`,
      rc: '00',
      type: 'UPI',
      exceptionType: 'HANGING',
      ttumRequired: Math.random() > 0.7,
      direction: i % 2 === 0 ? 'INWARD' : 'OUTWARD',
      reference: `REF${String(100000 + i).slice(-6)}`
    });
  }
  
  return hanging;
};

/**
 * Generate demo unmatched transactions (true unmatched)
 * Different from hanging - these have data in multiple systems but don't match
 */
export const generateDemoUnmatchedTransactions = () => {
  const unmatched: any[] = [];
  const today = new Date();
  
  for (let i = 0; i < 250; i++) {
    const amount = 1000 + Math.random() * 19000;
    // Generate dates in the last 30 days
    const daysAgo = i % 30;
    const date = new Date(today);
    date.setDate(date.getDate() - daysAgo);
    
    unmatched.push({
      rrn: `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}${String(date.getDate()).padStart(2, '0')}${String(200000 + i).slice(-6)}`,
      status: 'MISMATCH',
      cbs: {
        rrn: `CBS_${i}`,
        amount: amount,
        date: date.toLocaleDateString('en-GB'),
        reference: `CBS${i}`,
        debit_credit: i % 2 === 0 ? 'Cr' : 'Dr'
      },
      npci: {
        rrn: `NPCI_${i}`,
        amount: amount + (Math.random() > 0.5 ? 10 : -10), // Slight mismatch
        date: date.toLocaleDateString('en-GB'),
        reference: `NPCI${i}`,
        debit_credit: i % 2 === 0 ? 'Cr' : 'Dr'
      },
      cbs_source: 'X',
      npci_source: 'X',
      switch_source: '',
      suggested_action: 'Manual review required',
      zero_difference: false
    });
  }
  
  return unmatched;
};

/**
 * Check if we're in demo mode
 * Can be controlled via environment variable or always true for demo
 */
export const isDemoMode = (): boolean => {
  // Always demo mode for this MVP
  return true;
};