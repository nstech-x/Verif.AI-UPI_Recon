import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface DateContextType {
  dateFrom: string;
  dateTo: string;
  setDateFrom: (date: string) => void;
  setDateTo: (date: string) => void;
  setDateRange: (from: string, to: string) => void;
}

const DateContext = createContext<DateContextType | undefined>(undefined);

export const useDate = () => {
  const context = useContext(DateContext);
  if (context === undefined) {
    throw new Error('useDate must be used within a DateProvider');
  }
  return context;
};

interface DateProviderProps {
  children: ReactNode;
}

export const DateProvider = ({ children }: DateProviderProps) => {
  // Set default dates to current month
  const getDefaultDates = () => {
    const now = new Date();
    const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);

    const formatDate = (date: Date) => date.toISOString().split('T')[0];

    return {
      from: formatDate(firstDay),
      to: formatDate(lastDay)
    };
  };

  const [dateFrom, setDateFrom] = useState(getDefaultDates().from);
  const [dateTo, setDateTo] = useState(getDefaultDates().to);

  const setDateRange = (from: string, to: string) => {
    setDateFrom(from);
    setDateTo(to);
  };

  // Load from localStorage on mount
  useEffect(() => {
    const savedFrom = localStorage.getItem('global-date-from');
    const savedTo = localStorage.getItem('global-date-to');

    if (savedFrom && savedTo) {
      setDateFrom(savedFrom);
      setDateTo(savedTo);
    }
  }, []);

  // Save to localStorage when dates change
  useEffect(() => {
    localStorage.setItem('global-date-from', dateFrom);
    localStorage.setItem('global-date-to', dateTo);
  }, [dateFrom, dateTo]);

  const value = {
    dateFrom,
    dateTo,
    setDateFrom,
    setDateTo,
    setDateRange
  };

  return (
    <DateContext.Provider value={value}>
      {children}
    </DateContext.Provider>
  );
};
