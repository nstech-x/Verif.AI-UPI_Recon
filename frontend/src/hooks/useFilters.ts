import { useState, useMemo } from 'react';
import { DemoSummaryData, DemoHistoricalData } from '../lib/demoData';
import { SummaryResponse } from '../lib/api';

export interface FilterState {
  dateFrom: string;
  dateTo: string;
  status: string;
  amountMin: string;
  amountMax: string;
  bank: string;
  cycle: string;
  transactionType: string;
  reconResult: string;
}

export const useFilters = (
  summaryData: SummaryResponse | DemoSummaryData | null,
  historicalData: DemoHistoricalData[]
) => {
  const [filters, setFilters] = useState<FilterState>({
    dateFrom: '',
    dateTo: '',
    status: 'all',
    amountMin: '',
    amountMax: '',
    bank: 'all',
    cycle: 'all',
    transactionType: 'all',
    reconResult: 'all'
  });

  // Update individual filter
  const updateFilter = (key: keyof FilterState, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  // Update date range
  const updateDateRange = (dateFrom: string, dateTo: string) => {
    setFilters(prev => ({ ...prev, dateFrom, dateTo }));
  };

  // Reset all filters
  const resetFilters = () => {
    setFilters({
      dateFrom: '',
      dateTo: '',
      status: 'all',
      amountMin: '',
      amountMax: '',
      bank: 'all',
      cycle: 'all',
      transactionType: 'all',
      reconResult: 'all'
    });
  };

  // Filtered summary data
  const filteredSummary = useMemo(() => {
    if (!summaryData) return null;

    // Apply filters to summary data
    let filtered = { ...summaryData };

    // Status filter affects counts
    if (filters.status !== 'all') {
      const statusMap: Record<string, keyof DemoSummaryData> = {
        'matched': 'matched',
        'unmatched': 'unmatched',
        'partial': 'partial_matches',
        'hanging': 'hanging'
      };
      
      const statusKey = statusMap[filters.status];
      if (statusKey && filtered[statusKey]) {
        // Show only selected status data
        const selectedData = filtered[statusKey] as { count: number; amount: number };
        filtered = {
          ...filtered,
          totals: {
            count: selectedData.count,
            amount: selectedData.amount
          }
        };
      }
    }

    return filtered;
  }, [summaryData, filters]);

  // Filtered historical data
  const filteredHistorical = useMemo(() => {
    if (!historicalData.length) return [];

    const parseDate = (value: string): Date | null => {
      if (!value) return null;
      if (value.length === 7) {
        // YYYY-MM
        return new Date(`${value}-01`);
      }
      if (value.length === 10) {
        // YYYY-MM-DD
        return new Date(value);
      }
      const dt = new Date(value);
      return isNaN(dt.getTime()) ? null : dt;
    };

    const fromDate = parseDate(filters.dateFrom);
    const toDate = parseDate(filters.dateTo);

    return historicalData.filter(item => {
      // Date filter (handle monthly buckets)
      if (fromDate || toDate) {
        if (item.month.length === 7) {
          const monthStart = new Date(`${item.month}-01`);
          const monthEnd = new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 0);
          if (fromDate && monthEnd < fromDate) return false;
          if (toDate && monthStart > toDate) return false;
        } else {
          const itemDate = parseDate(item.month);
          if (fromDate && itemDate && itemDate < fromDate) return false;
          if (toDate && itemDate && itemDate > toDate) return false;
        }
      }

      // Amount filter (using allTxns as proxy for amount)
      if (filters.amountMin && item.allTxns < parseInt(filters.amountMin)) return false;
      if (filters.amountMax && item.allTxns > parseInt(filters.amountMax)) return false;

      return true;
    });
  }, [historicalData, filters]);

  // Check if any filters are active
  const hasActiveFilters = useMemo(() => {
    return filters.status !== 'all' ||
           filters.amountMin !== '' ||
           filters.amountMax !== '' ||
           filters.bank !== 'all' ||
           filters.cycle !== 'all' ||
           filters.transactionType !== 'all' ||
           filters.reconResult !== 'all' ||
           filters.dateFrom !== '' ||
           filters.dateTo !== '';
  }, [filters]);

  return {
    filters,
    updateFilter,
    updateDateRange,
    resetFilters,
    filteredSummary,
    filteredHistorical,
    hasActiveFilters
  };
};
