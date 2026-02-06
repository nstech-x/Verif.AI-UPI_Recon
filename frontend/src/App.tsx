import { useState, useEffect } from "react";
import { Toaster } from "./components/ui/toaster";
import { Toaster as Sonner } from "./components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { DateProvider } from "./contexts/DateContext";
import { DemoDataProvider } from "./contexts/DemoDataContext";
import { clearAllFocus } from "./lib/focusUtils";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import FileUpload from "./pages/FileUpload";
import ViewStatus from "./pages/ViewStatus";
import Recon from "./pages/Recon";
import Unmatched from "./pages/Unmatched";
import Reports from "./pages/Reports";
import Enquiry from "./pages/Enquiry";
import ForceMatch from "./pages/ForceMatch";
import AutoMatch from "./pages/AutoMatch";
import Rollback from "./pages/Rollback";
import Audit from "./pages/Audit";
import NotFound from "./pages/NotFound";
import Login from "./pages/Login";
import WelcomeDialog from "./components/WelcomeDialog";
import AIShowcase from "./pages/AIShowcase";
import BlockchainAudit from "./pages/BlockchainAudit";
// import Watchlist from "./pages/Watchlist";
import MakerChecker from "./pages/MakerChecker";
import Disputes from "./pages/Disputes";
import CycleSkip from "./pages/CycleSkip";
import IncomeExpenseDashboard from "./pages/IncomeExpenseDashboard";

const queryClient = new QueryClient();

// Protected Route component
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

// App Routes component
const AppRoutes = () => {
  const location = useLocation();
  
  return (
    <Routes location={location} key={location.pathname}>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<ProtectedRoute><Layout><Dashboard /></Layout></ProtectedRoute>} />
      <Route path="/upload" element={<ProtectedRoute><Layout><FileUpload /></Layout></ProtectedRoute>} />
      <Route path="/file-upload" element={<ProtectedRoute><Layout><FileUpload /></Layout></ProtectedRoute>} />
      <Route path="/view-status" element={<ProtectedRoute><Layout><ViewStatus /></Layout></ProtectedRoute>} />
      <Route path="/recon" element={<ProtectedRoute><Layout><Recon /></Layout></ProtectedRoute>} />
      <Route path="/unmatched" element={<ProtectedRoute><Layout><Unmatched /></Layout></ProtectedRoute>} />
      <Route path="/force-match" element={<ProtectedRoute><Layout><ForceMatch /></Layout></ProtectedRoute>} />
      <Route path="/auto-match" element={<ProtectedRoute><Layout><AutoMatch /></Layout></ProtectedRoute>} />
      <Route path="/rollback" element={<ProtectedRoute><Layout><Rollback /></Layout></ProtectedRoute>} />
      <Route path="/enquiry" element={<ProtectedRoute><Layout><Enquiry /></Layout></ProtectedRoute>} />
      <Route path="/reports" element={<ProtectedRoute><Layout><Reports /></Layout></ProtectedRoute>} />
      <Route path="/audit" element={<ProtectedRoute><Layout><Audit /></Layout></ProtectedRoute>} />
      <Route path="/ai-showcase" element={<ProtectedRoute><Layout><AIShowcase /></Layout></ProtectedRoute>} />
      <Route path="/blockchain" element={<ProtectedRoute><Layout><BlockchainAudit /></Layout></ProtectedRoute>} />
      {/* <Route path="/watchlist" element={<ProtectedRoute><Layout><Watchlist /></Layout></ProtectedRoute>} /> */}
      <Route path="/dashboard/maker-checker" element={<ProtectedRoute><Layout><MakerChecker /></Layout></ProtectedRoute>} />
      <Route path="/dashboard/disputes" element={<ProtectedRoute><Layout><Disputes /></Layout></ProtectedRoute>} />
      <Route path="/cycle-skip" element={<ProtectedRoute><Layout><CycleSkip /></Layout></ProtectedRoute>} />
      <Route path="/income-expense" element={<ProtectedRoute><Layout><IncomeExpenseDashboard /></Layout></ProtectedRoute>} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
};

const App = () => {
  // Handle global click to prevent cursor blinking
  const handleGlobalClick = (event: React.MouseEvent) => {
    const target = event.target as HTMLElement;
    
    // Don't interfere with interactive elements
    const isInteractive = target.tagName === 'INPUT' ||
                          target.tagName === 'TEXTAREA' ||
                          target.tagName === 'BUTTON' ||
                          target.tagName === 'A' ||
                          target.hasAttribute('contenteditable') ||
                          target.closest('button') ||
                          target.closest('a') ||
                          target.closest('[role="button"]');
    
    if (!isInteractive) {
      // Clear any unwanted focus
      setTimeout(() => clearAllFocus(), 0);
    }
  };

  return (
    <div onClick={handleGlobalClick} className="min-h-screen">
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
            <DateProvider>
              <DemoDataProvider>
                <AuthProvider>
                  <AppRoutes />
                </AuthProvider>
              </DemoDataProvider>
            </DateProvider>
          </BrowserRouter>
        </TooltipProvider>
      </QueryClientProvider>
    </div>
  );
};

export default App;
