import axios, { AxiosInstance, AxiosResponse } from 'axios';

// API Base Configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "https://verif-ai.onrender.com";

// Create axios instance with default config
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 500000, // 8 min for file uploads
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for adding headers
api.interceptors.request.use(
  (config) => {
    // Add authentication token if available
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized access - Clear token and redirect
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      localStorage.removeItem('token_type');
      window.location.href = '/login';
      console.error('Unauthorized access');
    } else if (error.response?.status >= 500) {
      // Handle server errors
      console.error('Server error:', error.response.data);
    }
    return Promise.reject(error);
  }
);

// Export the api instance for use in other modules
export { api };

// TypeScript interfaces for API responses
export interface UploadResponse {
  status: string;
  message: string;
  run_id: string;
  folder: string;
  cbs_balance?: string;
  transaction_date?: string;
  next_step?: string;
  uploaded_files?: string[];
}

export interface ReconciliationResponse {
  status: string;
  run_id: string;
  output_folder: string;
  matched_count: number;
  unmatched_count: number;
  exception_count: number;
  partial_match_count: number;
  hanging_count: number;
}

export interface SummaryResponse {
  run_id: string;
  generated_at: string;
  totals: { count: number; amount: number };
  matched: { count: number; amount: number };
  unmatched: { count: number; amount: number };
  hanging: { count: number; amount: number };
  exceptions: { count: number; amount: number };
  status?: string;
  total_transactions?: number;
  adjustments?: number;
  partial_matches?: { count: number; amount: number };
  inflow_outflow?: {
    inward: { count: number; amount: number };
    outward: { count: number; amount: number };
  };
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
  inflow?: { count: number; amount: number };
  outflow?: { count: number; amount: number };
  breakdown?: any;
}

export interface ReportResponse {
  report_type: string;
  data?: any;
  count?: number;
  message?: string;
}

export interface ChatbotResponse {
  rrn?: string;
  details?: any;
  run_id?: string;
}

export interface ForceMatchResponse {
  status: string;
  message: string;
  action: string;
  rrn: string;
}

export interface RawDataResponse {
  run_id: string;
  data: any;
  summary: {
    total_rrns: number;
    matched_count: number;
    unmatched_count: number;
    exception_count: number;
    file_path: string;
  };
}

// API Functions
export const apiClient = {
  // File Upload
  uploadFiles: async (files: {
    cbs_inward: File;
    cbs_outward: File;
    switch: File;
    npci_inward?: File;
    npci_outward?: File;
    ntsl?: File;
    adjustment?: File;
    cbs_balance?: string;
    transaction_date?: string;
  }): Promise<UploadResponse> => {
    const formData = new FormData();
    
    // Add all files to the 'files' field
    Object.values(files).forEach(value => {
      if (value instanceof File) {
        formData.append('files', value);
      }
    });
    
    // Add metadata
    if (files.cbs_balance) {
      formData.append('cbs_balance', files.cbs_balance);
    }
    if (files.transaction_date) {
      formData.append('transaction_date', files.transaction_date);
    }

    const response: AxiosResponse<UploadResponse> = await api.post('/api/v1/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Reconciliation
  runReconciliation: async (runId?: string, direction: string = 'INWARD'): Promise<ReconciliationResponse> => {
    const body: any = {};
    if (runId) {
      body.run_id = runId;
    }
    const response: AxiosResponse<ReconciliationResponse> = await api.post('/api/v1/recon/run', 
      body,
      { params: { direction } }
    );
    return response.data;
  },

  // Summary
  getSummary: async (): Promise<SummaryResponse> => {
    const response: AxiosResponse<SummaryResponse> = await api.get('/api/v1/summary');
    return response.data;
  },

  // Historical Summary for Charts
  getHistoricalSummary: async (): Promise<any[]> => {
    const response: AxiosResponse<any[]> = await api.get('/api/v1/summary/historical');
    return response.data;
  },

  // Reports
  getReport: async (reportType: string): Promise<ReportResponse> => {
    const response: AxiosResponse<ReportResponse> = await api.get(`/api/v1/reports/${reportType}`);
    return response.data;
  },

  // Unmatched Transactions
  getLatestUnmatched: async (): Promise<any> => {
    const response: AxiosResponse<any> = await api.get('/api/v1/reports/unmatched');
    return response.data;
  },

  // Chatbot/Enquiry - Now directly integrated in main app
  getChatbotByRRN: async (rrn: string): Promise<ChatbotResponse> => {
    try {
      // Backend expects a query param `rrn` on /api/v1/chatbot
      const response: AxiosResponse<any> = await api.get('/api/v1/chatbot', { params: { rrn } });
      const data = response.data;

      // Normalize backend response into the ChatbotResponse shape expected by frontend
      return {
        rrn: data?.rrn || rrn,
        details: data || null,
        run_id: data?.recon_run_id || data?.run_id || undefined,
      };
    } catch (error: any) {
      // Handle 404 and other errors gracefully by returning error data
      if (error.response?.status === 404 && error.response?.data) {
        return {
          rrn: rrn,
          details: error.response.data, // Return the error response as details
          run_id: undefined,
        };
      }
      // Re-throw other errors
      throw error;
    }
  },

  getChatbotByTxnId: async (txnId: string): Promise<ChatbotResponse> => {
    try {
      const response: AxiosResponse<any> = await api.get('/api/v1/chatbot', {
        params: { txn_id: txnId },
      });
      const data = response.data;

      // Normalize backend response into the ChatbotResponse shape expected by frontend
      return {
        rrn: data?.rrn || undefined,
        details: data || null,
        run_id: data?.recon_run_id || data?.run_id || undefined,
      };
    } catch (error: any) {
      // Handle 404 and other errors gracefully by returning error data
      if (error.response?.status === 404 && error.response?.data) {
        return {
          rrn: undefined,
          details: error.response.data, // Return the error response as details
          run_id: undefined,
        };
      }
      // Re-throw other errors
      throw error;
    }
  },

  // Force Match
  forceMatch: async (rrn: string, source1: string, source2: string, action: string = 'match', lhsColumn?: string, rhsColumn?: string): Promise<ForceMatchResponse> => {
    const params: any = { rrn, source1, source2, action };
    if (lhsColumn) params.lhs_column = lhsColumn;
    if (rhsColumn) params.rhs_column = rhsColumn;
    const response: AxiosResponse<ForceMatchResponse> = await api.post('/api/v1/force-match', null, {
      params,
    });
    return response.data;
  },

  // Auto Match Parameters
  setAutoMatchParameters: async (params: {
    amount_tolerance: number;
    date_tolerance_days: number;
    enable_auto_match: boolean;
  }): Promise<any> => {
    const response: AxiosResponse = await api.post('/api/v1/auto-match/parameters', null, {
      params: params
    });
    return response.data;
  },

  // Rollback
  rollbackReconciliation: async (runId?: string): Promise<any> => {
    const response: AxiosResponse = await api.post('/api/v1/rollback', null, {
      params: runId ? { run_id: runId } : {},
    });
    return response.data;
  },

  // Raw Data
  getRawData: async (): Promise<RawDataResponse> => {
    const response: AxiosResponse<RawDataResponse> = await api.get('/api/v1/recon/latest/raw');
    return response.data;
  },

  // Upload Metadata
  getUploadMetadata: async (): Promise<any> => {
    const response: AxiosResponse<any> = await api.get('/api/v1/upload/metadata');
    return response.data;
  },

  // File Downloads
  downloadLatestReport: async (): Promise<AxiosResponse<Blob>> => {
    const response: AxiosResponse<Blob> = await api.get('/api/v1/recon/latest/report', {
      responseType: 'blob',
    });
    return response;
  },

  downloadLatestAdjustments: async (): Promise<AxiosResponse<Blob>> => {
    const response: AxiosResponse<Blob> = await api.get('/api/v1/recon/latest/adjustments', {
      responseType: 'blob',
    });
    return response;
  },

  downloadReport: async (endpoint: string): Promise<AxiosResponse<Blob>> => {
    const response: AxiosResponse<Blob> = await api.get(`/api/v1/reports/${endpoint}`, {
      responseType: 'blob',
    });
    return response;
  },

  // TTUM Downloads
  downloadTTUMCSV: async (runId?: string, cycleId?: string): Promise<AxiosResponse<Blob>> => {
    const params: any = {};
    if (runId) params.run_id = runId;
    if (cycleId) params.cycle_id = cycleId;

    const response: AxiosResponse<Blob> = await api.get(
      '/api/v1/reports/ttum/csv',
      {
        params,
        responseType: 'blob',
      }
    );
    return response;
  },

  downloadTTUMXLSX: async (runId?: string, cycleId?: string): Promise<AxiosResponse<Blob>> => {
    const params: any = {};
    if (runId) params.run_id = runId;
    if (cycleId) params.cycle_id = cycleId;

    const response: AxiosResponse<Blob> = await api.get(
      '/api/v1/reports/ttum/xlsx',
      {
        params,
        responseType: 'blob',
      }
    );
    return response;
  },

  downloadTTUMMerged: async (runId?: string, format: 'csv' | 'xlsx' = 'xlsx'): Promise<AxiosResponse<Blob>> => {
    const params: any = {
      format,
    };
    if (runId) params.run_id = runId;

    const response: AxiosResponse<Blob> = await api.get(
      '/api/v1/reports/ttum/merged',
      {
        params,
        responseType: 'blob',
      }
    );
    return response;
  },

  // Helper function to trigger file download
  triggerFileDownload: (blob: Blob, filename: string): void => {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  // Rollback Operations (Phase 3)
  rollbackWholeProcess: async (runId: string, reason: string = "User initiated whole process rollback"): Promise<any> => {
    const response: AxiosResponse = await api.post(
      `/api/v1/rollback/whole-process?run_id=${runId}&reason=${encodeURIComponent(reason)}`
    );
    return response.data;
  },

  rollbackIngestion: async (runId: string, filename: string, error: string = "User initiated rollback"): Promise<any> => {
    const response: AxiosResponse = await api.post(
      `/api/v1/rollback/ingestion?run_id=${runId}&filename=${filename}&error=${encodeURIComponent(error)}`
    );
    return response.data;
  },

  rollbackMidRecon: async (runId: string, error: string = "Critical error during reconciliation", affectedTransactions: string[] = []): Promise<any> => {
    const response: AxiosResponse = await api.post(
      `/api/v1/rollback/mid-recon?run_id=${runId}&error=${encodeURIComponent(error)}`
    );
    return response.data;
  },

  rollbackCycleWise: async (runId: string, cycleId: string): Promise<any> => {
    const response: AxiosResponse = await api.post(
      `/api/v1/rollback/cycle-wise?run_id=${runId}&cycle_id=${cycleId}`
    );
    return response.data;
  },

  rollbackAccounting: async (runId: string, reason: string = "User initiated accounting rollback", voucherIds: string[] = []): Promise<any> => {
    const response: AxiosResponse = await api.post(
      `/api/v1/rollback/accounting?run_id=${runId}&reason=${encodeURIComponent(reason)}`
    );
    return response.data;
  },

  getRollbackHistory: async (runId?: string): Promise<any> => {
    const url = runId ? `/api/v1/rollback/history?run_id=${runId}` : '/api/v1/rollback/history';
    const response: AxiosResponse = await api.get(url);
    return response.data;
  },

  getAvailableCycles: async (runId?: string): Promise<any> => {
    const url = runId ? `/api/v1/rollback/available-cycles?run_id=${runId}` : '/api/v1/rollback/available-cycles';
    const response: AxiosResponse = await api.get(url);
    return response.data;
  },

  // Exception Handling (Phase 3 Task 3)
  handleSFTPConnectionFailure: async (runId: string, host: string, error: string): Promise<any> => {
    const response: AxiosResponse = await api.post(
      `/api/v1/exception/sftp-connection?run_id=${runId}&host=${host}&error=${encodeURIComponent(error)}`
    );
    return response.data;
  },

  handleSFTPTimeout: async (runId: string, filename: string, timeoutSeconds: number): Promise<any> => {
    const response: AxiosResponse = await api.post(
      `/api/v1/exception/sftp-timeout?run_id=${runId}&filename=${filename}&timeout_seconds=${timeoutSeconds}`
    );
    return response.data;
  },

  handleDuplicateCycle: async (
    runId: string,
    cycleId: string,
    currentFilename: string,
    existingFilename: string
  ): Promise<any> => {
    const response: AxiosResponse = await api.post(
      `/api/v1/exception/duplicate-cycle?run_id=${runId}&cycle_id=${cycleId}&current_filename=${currentFilename}&existing_filename=${existingFilename}`
    );
    return response.data;
  },

  handleNetworkTimeout: async (runId: string, service: string, error: string): Promise<any> => {
    const response: AxiosResponse = await api.post(
      `/api/v1/exception/network-timeout?run_id=${runId}&service=${service}&error=${encodeURIComponent(error)}`
    );
    return response.data;
  },

  handleValidationError: async (runId: string, filename: string, errorDetails: any): Promise<any> => {
    const response: AxiosResponse = await api.post(
      `/api/v1/exception/validation-error?run_id=${runId}&filename=${filename}&error_details=${encodeURIComponent(JSON.stringify(errorDetails))}`
    );
    return response.data;
  },

  handleInsufficientSpace: async (runId: string, requiredBytes: number, availableBytes: number): Promise<any> => {
    const response: AxiosResponse = await api.post(
      `/api/v1/exception/insufficient-space?run_id=${runId}&required_bytes=${requiredBytes}&available_bytes=${availableBytes}`
    );
    return response.data;
  },

  handleDatabaseError: async (runId: string, error: string): Promise<any> => {
    const response: AxiosResponse = await api.post(
      `/api/v1/exception/database-error?run_id=${runId}&error=${encodeURIComponent(error)}`
    );
    return response.data;
  },

  getExceptionSummary: async (runId?: string): Promise<any> => {
    const url = runId ? `/api/v1/exception/summary?run_id=${runId}` : '/api/v1/exception/summary';
    const response: AxiosResponse = await api.get(url);
    return response.data;
  },

  getRunExceptions: async (runId: string): Promise<any> => {
    const response: AxiosResponse = await api.get(`/api/v1/exception/run/${runId}`);
    return response.data;
  },

  resolveException: async (exceptionId: string): Promise<any> => {
    const response: AxiosResponse = await api.post(`/api/v1/exception/resolve/${exceptionId}`);
    return response.data;
  },

  // GL Justification & Proofing (Phase 3 Task 4)
  createGLProofingReport: async (
    runId: string,
    reportDate: string,
    glAccounts: any[],
    varianceBridges: any[]
  ): Promise<any> => {
    const response: AxiosResponse = await api.post(
      `/api/v1/gl/proofing/create?run_id=${runId}&report_date=${reportDate}&gl_accounts=${encodeURIComponent(JSON.stringify(glAccounts))}&variance_bridges=${encodeURIComponent(JSON.stringify(varianceBridges))}`
    );
    return response.data;
  },

  addVarianceBridge: async (
    runId: string,
    category: string,
    description: string,
    amount: number,
    justification: string,
    transactionDate?: string,
    reportDate?: string
  ): Promise<any> => {
    const params = new URLSearchParams({
      run_id: runId,
      category,
      description,
      amount: amount.toString(),
      justification,
      ...(transactionDate && { transaction_date: transactionDate }),
      ...(reportDate && { report_date: reportDate })
    });

    const response: AxiosResponse = await api.post(`/api/v1/gl/proofing/bridge?${params.toString()}`);
    return response.data;
  },

  getProofingReport: async (reportId: string): Promise<any> => {
    const response: AxiosResponse = await api.get(`/api/v1/gl/proofing/report/${reportId}`);
    return response.data;
  },

  getAllProofingReports: async (): Promise<any> => {
    const response: AxiosResponse = await api.get('/api/v1/gl/proofing/reports');
    return response.data;
  },

  getUnreconciledAccounts: async (runId: string): Promise<any> => {
    const response: AxiosResponse = await api.get(`/api/v1/gl/proofing/unreconciled/${runId}`);
    return response.data;
  },

  getHighPriorityBridges: async (runId: string): Promise<any> => {
    const response: AxiosResponse = await api.get(`/api/v1/gl/proofing/high-priority/${runId}`);
    return response.data;
  },

  getAgingSummary: async (runId: string): Promise<any> => {
    const response: AxiosResponse = await api.get(`/api/v1/gl/proofing/aging/${runId}`);
    return response.data;
  },

  resolveVarianceBridge: async (bridgeId: string, resolvedBy: string = "System"): Promise<any> => {
    const response: AxiosResponse = await api.post(
      `/api/v1/gl/proofing/bridge/resolve/${bridgeId}?resolved_by=${encodeURIComponent(resolvedBy)}`
    );
    return response.data;
  },

  // Audit Trail & Logging (Phase 3 Task 5)
  getAuditTrail: async (runId: string): Promise<any> => {
    const response: AxiosResponse = await api.get(`/api/v1/audit/trail/${runId}`);
    return response.data;
  },

  getUserActions: async (userId: string, limit: number = 100): Promise<any> => {
    const response: AxiosResponse = await api.get(
      `/api/v1/audit/user/${userId}?limit=${limit}`
    );
    return response.data;
  },

  getAuditSummary: async (runId?: string): Promise<any> => {
    const url = runId ? `/api/v1/audit/summary?run_id=${runId}` : '/api/v1/audit/summary';
    const response: AxiosResponse = await api.get(url);
    return response.data;
  },

  getActionsByDateRange: async (startDate: string, endDate: string): Promise<any> => {
    const response: AxiosResponse = await api.get(
      `/api/v1/audit/date-range?start_date=${startDate}&end_date=${endDate}`
    );
    return response.data;
  },

  logCustomAction: async (
    runId: string,
    action: string,
    userId?: string,
    level: string = "INFO",
    details: any = {}
  ): Promise<any> => {
    const params = new URLSearchParams({
      run_id: runId,
      action,
      level,
      details: JSON.stringify(details),
      ...(userId && { user_id: userId })
    });

    const response: AxiosResponse = await api.post(`/api/v1/audit/log-action?${params.toString()}`);
    return response.data;
  },

  generateComplianceReport: async (
    runId: string,
    reportType: string = "full"
  ): Promise<any> => {
    const response: AxiosResponse = await api.get(
      `/api/v1/audit/compliance/${runId}?report_type=${reportType}`
    );
    return response.data;
  },

  logReconEvent: async (
    runId: string,
    event: string,
    userId?: string,
    matchedCount: number = 0,
    unmatchedCount: number = 0,
    error?: string
  ): Promise<any> => {
    const params = new URLSearchParams({
      run_id: runId,
      event,
      matched_count: matchedCount.toString(),
      unmatched_count: unmatchedCount.toString(),
      ...(userId && { user_id: userId }),
      ...(error && { error })
    });

    const response: AxiosResponse = await api.post(`/api/v1/audit/event/recon?${params.toString()}`);
    return response.data;
  },

  logRollbackEvent: async (
    runId: string,
    rollbackLevel: string,
    userId?: string,
    status: string = "completed"
  ): Promise<any> => {
    const params = new URLSearchParams({
      run_id: runId,
      rollback_level: rollbackLevel,
      status,
      ...(userId && { user_id: userId })
    });

    const response: AxiosResponse = await api.post(`/api/v1/audit/event/rollback?${params.toString()}`);
    return response.data;
  },

  logForceMatchEvent: async (
    runId: string,
    rrn: string,
    source1: string,
    source2: string,
    userId?: string
  ): Promise<any> => {
    const params = new URLSearchParams({
      run_id: runId,
      rrn,
      source1,
      source2,
      ...(userId && { user_id: userId })
    });

    const response: AxiosResponse = await api.post(`/api/v1/audit/event/force-match?${params.toString()}`);
    return response.data;
  },

  logGLEvent: async (
    runId: string,
    operation: string,
    userId?: string,
    details: any = {}
  ): Promise<any> => {
    const params = new URLSearchParams({
      run_id: runId,
      operation,
      details: JSON.stringify(details),
      ...(userId && { user_id: userId })
    });

    const response: AxiosResponse = await api.post(`/api/v1/audit/event/gl?${params.toString()}`);
    return response.data;
  },

  // Health Check
  healthCheck: async (): Promise<any> => {
    const response: AxiosResponse = await api.get('/health');
    return response.data;
  },

  // Income & Expense APIs
  getIncomeExpenseData: async (dateFrom: string, dateTo: string): Promise<any> => {
    const response: AxiosResponse = await api.get('/api/v1/income-expense/data', {
      params: { date_from: dateFrom, date_to: dateTo }
    });
    return response.data;
  },

  downloadIncomeExpenseExcel: async (dateFrom: string, dateTo: string): Promise<AxiosResponse<Blob>> => {
    const response: AxiosResponse<Blob> = await api.get('/api/v1/income-expense/download-excel', {
      params: { date_from: dateFrom, date_to: dateTo },
      responseType: 'blob'
    });
    return response;
  },
};

export default apiClient;
