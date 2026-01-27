import { createContext, useContext, useState, ReactNode } from 'react';
import { generateDemoSummary, generateDemoHistorical, DemoSummaryData, DemoHistoricalData } from '../lib/demoData';

interface DemoDataContextType {
  isDemoMode: boolean;
  setDemoMode: (enabled: boolean) => void;
  demoSummary: DemoSummaryData | null;
  demoHistorical: DemoHistoricalData[];
  triggerDemoData: () => void;
  clearDemoData: () => void;
}

const DemoDataContext = createContext<DemoDataContextType | undefined>(undefined);

export const useDemoData = () => {
  const context = useContext(DemoDataContext);
  if (context === undefined) {
    throw new Error('useDemoData must be used within a DemoDataProvider');
  }
  return context;
};

interface DemoDataProviderProps {
  children: ReactNode;
}

export const DemoDataProvider = ({ children }: DemoDataProviderProps) => {
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [demoSummary, setDemoSummary] = useState<DemoSummaryData | null>(null);
  const [demoHistorical, setDemoHistorical] = useState<DemoHistoricalData[]>([]);

  const setDemoMode = (enabled: boolean) => {
    setIsDemoMode(enabled);
    if (!enabled) {
      clearDemoData();
    }
  };

  const triggerDemoData = () => {
    setIsDemoMode(true);
    setDemoSummary(generateDemoSummary());
    setDemoHistorical(generateDemoHistorical());
  };

  const clearDemoData = () => {
    setDemoSummary(null);
    setDemoHistorical([]);
  };

  const value = {
    isDemoMode,
    setDemoMode,
    demoSummary,
    demoHistorical,
    triggerDemoData,
    clearDemoData
  };

  return (
    <DemoDataContext.Provider value={value}>
      {children}
    </DemoDataContext.Provider>
  );
};