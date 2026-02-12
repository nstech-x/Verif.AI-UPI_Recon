import { useState, useEffect, useMemo, useReducer } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Loader2, CheckCircle2, AlertCircle, Search, RefreshCw, ZoomIn } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { apiClient } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { generateDemoUnmatchedTransactions } from "@/lib/demoData";





// Constants
const TRANSACTION_STATUSES = ['PARTIAL_MATCH', 'HANGING', 'MISMATCH', 'PARTIAL_MISMATCH'] as const;
type TransactionStatus = typeof TRANSACTION_STATUSES[number];

const COMPARABLE_COLUMNS = ['amount', 'date', 'reference'] as const;
type ComparableColumn = typeof COMPARABLE_COLUMNS[number];

const SYSTEM_SOURCES = ['cbs', 'switch', 'npci'] as const;
type SystemSource = typeof SYSTEM_SOURCES[number];

interface TransactionDetail {
  rrn: string;
  amount: number;
  date: string;
  time?: string;
  description?: string;
  reference?: string;
  debit_credit?: string;
  status?: string;
}

interface Transaction {
  rrn: string;
  status: TransactionStatus;
  cbs?: TransactionDetail;
  switch?: TransactionDetail;
  npci?: TransactionDetail;
  cbs_source?: string;
  switch_source?: string;
  npci_source?: string;
  suggested_action?: string;
  zero_difference?: boolean;
}

interface ForceMatchState {
  transactions: Transaction[];
  loading: boolean;
  searchTerm: string;
  statusFilter: "all" | TransactionStatus;
  selectedTransaction: Transaction | null;
  showDualPanelDialog: boolean;
  panelLHS: SystemSource;
  panelRHS: SystemSource;
  isMatching: boolean;
  zeroDifferenceValid: boolean;
  panelLHSColumn: ComparableColumn;
  panelRHSColumn: ComparableColumn;
  matchingMode: "best_match" | "relaxed_match";
  showRCRB: boolean;
}

type ForceMatchAction =
  | { type: 'FETCH_START' }
  | { type: 'FETCH_SUCCESS'; payload: Transaction[] }
  | { type: 'FETCH_ERROR' }
  | { type: 'SET_SEARCH_TERM'; payload: string }
  | { type: 'SET_STATUS_FILTER'; payload: "all" | TransactionStatus }
  | { type: 'OPEN_DUAL_PANEL'; payload: Transaction }
  | { type: 'CLOSE_DUAL_PANEL' }
  | { type: 'SET_PANEL_LHS'; payload: SystemSource }
  | { type: 'SET_PANEL_RHS'; payload: SystemSource }
  | { type: 'SET_PANEL_LHS_COLUMN'; payload: ComparableColumn }
  | { type: 'SET_PANEL_RHS_COLUMN'; payload: ComparableColumn }
  | { type: 'SET_ZERO_DIFFERENCE_VALID'; payload: boolean }
  | { type: 'MATCH_START' }
  | { type: 'MATCH_FINISH' }
  | { type: 'SET_MATCHING_MODE'; payload: "best_match" | "relaxed_match" }
  | { type: 'TOGGLE_RC_RB'; payload: boolean };

const initialState: ForceMatchState = {
  transactions: [],
  loading: true,
  searchTerm: "",
  statusFilter: "all",
  selectedTransaction: null,
  showDualPanelDialog: false,
  panelLHS: "cbs",
  panelRHS: "switch",
  isMatching: false,
  zeroDifferenceValid: false,
  panelLHSColumn: "amount",
  panelRHSColumn: "amount",
  matchingMode: "best_match",
  showRCRB: false,
};

const forceMatchReducer = (state: ForceMatchState, action: ForceMatchAction): ForceMatchState => {
  switch (action.type) {
    case 'FETCH_START':
      return { ...state, loading: true };
    case 'FETCH_SUCCESS':
      return { ...state, loading: false, transactions: action.payload };
    case 'FETCH_ERROR':
      return { ...state, loading: false, transactions: [] };
    case 'SET_SEARCH_TERM':
      return { ...state, searchTerm: action.payload };
    case 'SET_STATUS_FILTER':
      return { ...state, statusFilter: action.payload };
    case 'OPEN_DUAL_PANEL':
      return { ...state, showDualPanelDialog: true, selectedTransaction: action.payload };
    case 'CLOSE_DUAL_PANEL':
      return { ...state, showDualPanelDialog: false, selectedTransaction: null, isMatching: false };
    case 'SET_PANEL_LHS':
      return { ...state, panelLHS: action.payload };
    case 'SET_PANEL_RHS':
      return { ...state, panelRHS: action.payload };
    case 'SET_PANEL_LHS_COLUMN':
      return { ...state, panelLHSColumn: action.payload };
    case 'SET_PANEL_RHS_COLUMN':
      return { ...state, panelRHSColumn: action.payload };
    case 'SET_ZERO_DIFFERENCE_VALID':
      return { ...state, zeroDifferenceValid: action.payload };
    case 'MATCH_START':
      return { ...state, isMatching: true };
    case 'MATCH_FINISH':
      return { ...state, isMatching: false };
    case 'SET_MATCHING_MODE':
      return { ...state, matchingMode: action.payload };
    case 'TOGGLE_RC_RB':
      return { ...state, showRCRB: action.payload };
    default:
      return state;
  }
};

  const transformRawDataToTransactions = (rawData: any): Transaction[] => {
  // Handle both formats: { data: {...} } and { exceptions: {...} }
  let dataToProcess = rawData?.data || rawData?.exceptions || {};
  
  if (!dataToProcess || Object.keys(dataToProcess).length === 0) {
    console.warn("No data found in API response");
    return [];
  }

  console.log("Processing transactions:", Object.keys(dataToProcess).length);

  return Object.entries(dataToProcess).map(([key, record]: [string, any]) => {
    // Use RRN from record data if available, otherwise use the key
    // Ensure we're using the actual RRN field, not transaction_id
    const rrn = record?.rrn || record?.RRN || key;

    const createDetail = (sourceData: any): TransactionDetail | undefined => {
      if (!sourceData) return undefined;

      // Extract RRN - prioritize rrn/RRN fields over transaction_id
      let detailRrn = sourceData.rrn || sourceData.RRN || rrn;
      
      // Extract reference/transaction ID separately from RRN
      let reference = sourceData.upi_tran_id || sourceData.UPI_Tran_ID || 
                       sourceData.transaction_id || sourceData.reference || '-';

      // Check if RRN field actually contains a transaction ID (starts with TXN)
      if (detailRrn && (detailRrn.startsWith('TXN') || detailRrn.startsWith('txn'))) {
        reference = detailRrn; // The "RRN" field is actually the transaction ID
        // Try to find actual RRN in other fields
        detailRrn = sourceData.RRN || sourceData.actual_rrn || sourceData.retrieval_reference_number || 
                   sourceData.reference_number || sourceData.upi_rrn || rrn;
      }

      return {
        rrn: detailRrn,
        amount: parseFloat(sourceData.amount) || 0,
        date: sourceData.date || sourceData.tran_date || '-',
        time: sourceData.time,
        description: sourceData.description,
        reference: reference,
        debit_credit: sourceData.debit_credit || sourceData.dr_cr,
        status: sourceData.status
      };
    };

    const cbs = createDetail(record.cbs);
    const switchTxn = createDetail(record.switch);
    const npci = createDetail(record.npci);

    // Calculate zero difference
    const amounts = [cbs?.amount, switchTxn?.amount, npci?.amount]
      .filter(a => a !== undefined && a !== null && !isNaN(a));
    const zeroDiff = amounts.length > 1 && amounts.every(a => a === amounts[0]);

    return {
      rrn,
      status: record.status || 'HANGING',
      cbs,
      switch: switchTxn,
      npci,
      cbs_source: cbs ? 'X' : '',
      switch_source: switchTxn ? 'X' : '',
      npci_source: npci ? 'X' : '',
      suggested_action: getSuggestedAction(record),
      zero_difference: zeroDiff
    };
  });
};

const getSuggestedAction = (record: any): string => {
  const status = record.status;
  if (status === 'HANGING') {
    const missing = [];
    if (!record.cbs) missing.push('CBS');
    if (!record.switch) missing.push('Switch');
    if (!record.npci) missing.push('NPCI');
    return `Investigate missing in ${missing.join(', ')}`;
  } else if (status === 'PARTIAL_MATCH') {
    const missing = [];
    if (!record.cbs) missing.push('CBS');
    if (!record.switch) missing.push('Switch');
    if (!record.npci) missing.push('NPCI');
    return `Check missing system data in ${missing.join(', ')}`;
  } else if (status === 'MISMATCH') {
    return 'CRITICAL: All systems have record but amounts/dates differ';
  } else if (status === 'PARTIAL_MISMATCH') {
    return 'WARNING: 2 systems have record but amounts/dates differ';
  }
  return 'Manual review required';
};

export default function ForceMatch() {
  const { toast } = useToast();
  const [state, dispatch] = useReducer(forceMatchReducer, initialState);
  const {
    transactions,
    loading,
    searchTerm,
    statusFilter,
    selectedTransaction,
    showDualPanelDialog,
    panelLHS,
    panelRHS,
    isMatching,
    zeroDifferenceValid,
    panelLHSColumn,
    panelRHSColumn,
  } = state;

  useEffect(() => {
    fetchUnmatchedTransactions();
  }, []);

  // Add polling mechanism - refetch every 30 seconds
  useEffect(() => {
    const pollInterval = setInterval(() => {
      fetchUnmatchedTransactions();
    }, 30000); // Poll every 30 seconds

    return () => clearInterval(pollInterval);
  }, []);

  useEffect(() => {
    if (selectedTransaction) validateZeroDifference(selectedTransaction);
  }, [panelLHS, panelRHS, panelLHSColumn, panelRHSColumn, selectedTransaction]);

  const fetchUnmatchedTransactions = async () => {
    try {
      dispatch({ type: 'FETCH_START' });
      const response = await apiClient.getRawData();
      console.log("API Response:", response);

      // Transform API response to expected format
      const transformedData = transformRawDataToTransactions(response);
      console.log("Real data loaded:", transformedData.length);
      dispatch({ type: 'FETCH_SUCCESS', payload: transformedData });
    } catch (error) {
      console.error('Failed to fetch raw data:', error);
      toast({
        title: "Error",
        description: "Failed to load unmatched transactions. Please try again.",
        variant: "destructive"
      });
      dispatch({ type: 'FETCH_ERROR' });
    }
  };

  const validateZeroDifference = (transaction: Transaction) => {
    const lhsCol = panelLHSColumn || 'amount';
    const rhsCol = panelRHSColumn || 'amount';
    const lhsValue = transaction?.[panelLHS]?.[lhsCol];
    const rhsValue = transaction?.[panelRHS]?.[rhsCol];

    const normalize = (v: any) => {
      if (v === undefined || v === null) return null;
      if (typeof v === 'number') return v;
      if (typeof v === 'string') return v.replace(/[₹,\s]/g, '');
      return String(v);
    };

    const l = normalize(lhsValue);
    const r = normalize(rhsValue);

    if (l === null || r === null) {
      dispatch({ type: 'SET_ZERO_DIFFERENCE_VALID', payload: false });
      return;
    }

    const lNum = Number(l);
    const rNum = Number(r);
    if (!isNaN(lNum) && !isNaN(rNum)) {
      dispatch({ type: 'SET_ZERO_DIFFERENCE_VALID', payload: Math.abs(lNum - rNum) < 0.0001 });
      return;
    }

    dispatch({ type: 'SET_ZERO_DIFFERENCE_VALID', payload: String(l) === String(r) });
  };

  const confirmForceMatch = async () => {
    if (!selectedTransaction) return;

    try {
      dispatch({ type: 'MATCH_START' });

      if (!zeroDifferenceValid) {
        toast({
          title: "Match Prevented",
          description: "Cannot force match with variance. The selected columns must have identical values.",
          variant: "destructive"
        });
        return;
      }

      await apiClient.forceMatch(
        selectedTransaction.rrn,
        panelLHS,
        panelRHS,
        'match',
        panelLHSColumn || 'amount',
        panelRHSColumn || 'amount'
      );

      toast({
        title: "Success",
        description: `RRN ${selectedTransaction.rrn} has been force matched between ${panelLHS.toUpperCase()} and ${panelRHS.toUpperCase()}`,
      });

      await fetchUnmatchedTransactions();
      dispatch({ type: 'CLOSE_DUAL_PANEL' });
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to force match. Please try again.",
        variant: "destructive"
      });
    } finally {
      dispatch({ type: 'MATCH_FINISH' });
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, string> = {
      'MATCHED': 'bg-green-500 text-white',
      'PARTIAL_MATCH': 'bg-yellow-500 text-white',
      'HANGING': 'bg-orange-500 text-white',
      'MISMATCH': 'bg-red-500 text-white',
      'PARTIAL_MISMATCH': 'bg-red-400 text-white',
      'FORCE_MATCHED': 'bg-blue-500 text-white'
    };

    const className = variants[status] || 'bg-gray-500 text-white';

    return (
      <Badge className={className}>
        {status.replace('_', ' ')}
      </Badge>
    );
  };

  const filteredTransactions = useMemo(() => {
    return transactions.filter(t => {
      const matchesSearch = !searchTerm || t.rrn.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'all' || t.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [transactions, searchTerm, statusFilter]);

  const summaryCounts = useMemo(() => {
    return transactions.reduce((acc, t) => {
      if (t.status === 'PARTIAL_MATCH') acc.partialMatch++;
      if (t.status === 'HANGING') acc.hanging++;
      if (t.status.includes('MISMATCH')) acc.mismatch++;
      return acc;
    }, { partialMatch: 0, hanging: 0, mismatch: 0 });
  }, [transactions]);

  return (
    <div className="p-6 space-y-6 min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Force Match</h1>
          <p className="text-gray-600">Dual-panel transaction matching with zero-difference validation</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchUnmatchedTransactions}
          disabled={loading}
          className="gap-2"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      <Alert className="border-blue-200 bg-blue-50">
        <ZoomIn className="h-4 w-4 text-blue-600" />
        <AlertTitle className="text-blue-900">Dual-Panel Matching</AlertTitle>
        <AlertDescription className="text-blue-800">
          Select two systems (LHS vs RHS) to compare amounts, dates, and references side-by-side. Zero-difference validation ensures perfect alignment before matching.
        </AlertDescription>
      </Alert>


      {/* RC RB (Deemed Success) View */}
      {state.showRCRB && (
        <Card className="shadow-lg border-amber-200">
          <CardHeader>
            <CardTitle className="text-amber-900">RC RB - Deemed Success Transactions</CardTitle>
          </CardHeader>
          <CardContent>
            <Alert className="border-amber-200 bg-amber-50 mb-4">
              <AlertCircle className="h-4 w-4 text-amber-600" />
              <AlertTitle className="text-amber-900">Response Code RB Transactions</AlertTitle>
              <AlertDescription className="text-amber-800">
                These transactions have Response Code RB and may be deemed successful. Identify TCC 102/103 based on CBS credit entry status.
              </AlertDescription>
            </Alert>
            <Button className="w-full rounded-full bg-amber-600 hover:bg-amber-700">
              Identify TCC 102/103
            </Button>
          </CardContent>
        </Card>
      )}

      <Card className="shadow-lg">
        <CardContent className="pt-6">
          <div className="flex gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search by RRN..."
                value={searchTerm}
                onChange={(e) => dispatch({ type: 'SET_SEARCH_TERM', payload: e.target.value })}
                className="pl-10"
              />
            </div>
            <div className="w-64">
              <Select value={statusFilter} onValueChange={(value) => dispatch({ type: 'SET_STATUS_FILTER', payload: value as "all" | TransactionStatus })}>
                <SelectTrigger>
                  <SelectValue placeholder="Filter by Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Unmatched Statuses</SelectItem>
                  {TRANSACTION_STATUSES.map(status => (
                    <SelectItem key={status} value={status}>{status.replace('_', ' ')}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{filteredTransactions.length}</div>
            <div className="text-sm text-gray-600">Total Unmatched</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-yellow-600">{summaryCounts.partialMatch}</div>
            <div className="text-sm text-gray-600">Partial Match</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-orange-600">{summaryCounts.hanging}</div>
            <div className="text-sm text-gray-600">Hanging</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-red-600">{summaryCounts.mismatch}</div>
            <div className="text-sm text-gray-600">Mismatches</div>
          </CardContent>
        </Card>
      </div>

      <Card className="shadow-lg">
        <CardHeader>
          <CardTitle>Transactions Requiring Attention</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
            </div>
          ) : filteredTransactions.length === 0 ? (
            <div className="text-center py-8">
              <CheckCircle2 className="w-12 h-12 mx-auto text-green-500 mb-2" />
              <p className="text-gray-600">No unmatched transactions found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-3">RRN</th>
                    <th className="text-left p-3">Status</th>
                    <th className="text-center p-3">CBS</th>
                    <th className="text-center p-3">Switch</th>
                    <th className="text-center p-3">NPCI</th>
                    <th className="text-left p-3">CBS Amount</th>
                    <th className="text-left p-3">Switch Amount</th>
                    <th className="text-left p-3">NPCI Amount</th>
                    <th className="text-left p-3">Zero Diff</th>
                    <th className="text-right p-3">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTransactions.map((transaction) => (
                    <tr key={transaction.rrn} className="border-b hover:bg-gray-50">
                      <td className="p-3 font-mono font-medium">{transaction.rrn}</td>
                      <td className="p-3">{getStatusBadge(transaction.status)}</td>
                      <td className="p-3 text-center">
                        {transaction.cbs ? <CheckCircle2 className="w-4 h-4 text-green-500 mx-auto" /> : <AlertCircle className="w-4 h-4 text-red-500 mx-auto" />}
                      </td>
                      <td className="p-3 text-center">
                        {transaction.switch ? <CheckCircle2 className="w-4 h-4 text-green-500 mx-auto" /> : <AlertCircle className="w-4 h-4 text-red-500 mx-auto" />}
                      </td>
                      <td className="p-3 text-center">
                        {transaction.npci ? <CheckCircle2 className="w-4 h-4 text-green-500 mx-auto" /> : <AlertCircle className="w-4 h-4 text-red-500 mx-auto" />}
                      </td>
                      <td className="p-3 font-semibold">
                        {transaction.cbs?.amount !== undefined && transaction.cbs?.amount !== null
                          ? `₹${transaction.cbs.amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                          : '-'}
                      </td>
                      <td className="p-3 font-semibold">
                        {transaction.switch?.amount !== undefined && transaction.switch?.amount !== null
                          ? `₹${transaction.switch.amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                          : '-'}
                      </td>
                      <td className="p-3 font-semibold">
                        {transaction.npci?.amount !== undefined && transaction.npci?.amount !== null
                          ? `₹${transaction.npci.amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                          : '-'}
                      </td>
                      <td className="p-3">
                        {transaction.zero_difference ? (
                          <Badge className="bg-green-500 text-white flex items-center gap-1 w-fit">
                            <CheckCircle2 className="h-3 w-3" /> Zero
                          </Badge>
                        ) : (
                          <Badge className="bg-red-500 text-white">Has Variance</Badge>
                        )}
                      </td>
                      <td className="p-3 text-right">
                        <Button
                          size="sm"
                          onClick={() => dispatch({ type: 'OPEN_DUAL_PANEL', payload: transaction })}
                          className="rounded-full bg-blue-500 hover:bg-blue-600 gap-2"
                        >
                          <ZoomIn className="w-4 h-4" />
                          Open Panel
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {showDualPanelDialog && selectedTransaction && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-auto">
            <div className="p-6 border-b">
              <h2 className="text-2xl font-bold">Transaction Matcher</h2>
              <p className="text-sm text-gray-600">RRN: {selectedTransaction.rrn}</p>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium">Left Panel System</label>
                  <Select value={panelLHS} onValueChange={(v) => dispatch({ type: 'SET_PANEL_LHS', payload: v as SystemSource })}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {selectedTransaction.cbs && <SelectItem value="cbs">CBS</SelectItem>}
                      {selectedTransaction.switch && <SelectItem value="switch">Switch</SelectItem>}
                      {selectedTransaction.npci && <SelectItem value="npci">NPCI</SelectItem>}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-sm font-medium">Right Panel System</label>
                  <Select value={panelRHS} onValueChange={(v) => dispatch({ type: 'SET_PANEL_RHS', payload: v as SystemSource })}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {selectedTransaction.cbs && <SelectItem value="cbs">CBS</SelectItem>}
                      {selectedTransaction.switch && <SelectItem value="switch">Switch</SelectItem>}
                      {selectedTransaction.npci && <SelectItem value="npci">NPCI</SelectItem>}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Card className="bg-blue-50">
                  <CardHeader>
                    <CardTitle className="text-lg">{panelLHS.toUpperCase()}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div><strong>RRN:</strong> {selectedTransaction[panelLHS]?.rrn || selectedTransaction.rrn}</div>
                      <div><strong>Amount:</strong> ₹{selectedTransaction[panelLHS]?.amount?.toLocaleString()}</div>
                      <div><strong>Date:</strong> {selectedTransaction[panelLHS]?.date}</div>
                      <div><strong>Transaction ID:</strong> {selectedTransaction[panelLHS]?.reference || '-'}</div>
                    </div>
                  </CardContent>
                </Card>
                <Card className="bg-green-50">
                  <CardHeader>
                    <CardTitle className="text-lg">{panelRHS.toUpperCase()}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div><strong>RRN:</strong> {selectedTransaction[panelRHS]?.rrn || selectedTransaction.rrn}</div>
                      <div><strong>Amount:</strong> ₹{selectedTransaction[panelRHS]?.amount?.toLocaleString()}</div>
                      <div><strong>Date:</strong> {selectedTransaction[panelRHS]?.date}</div>
                      <div><strong>Transaction ID:</strong> {selectedTransaction[panelRHS]?.reference || '-'}</div>
                    </div>
                  </CardContent>
                </Card>
              </div>

              <Alert className={zeroDifferenceValid ? "border-green-300 bg-green-50" : "border-red-300 bg-red-50"}>
                {zeroDifferenceValid ? (
                  <>
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    <AlertTitle className="text-green-800">Perfect Match</AlertTitle>
                    <AlertDescription className="text-green-700">
                      Amounts match exactly. Ready to proceed.
                    </AlertDescription>
                  </>
                ) : (
                  <>
                    <AlertCircle className="h-4 w-4 text-red-600" />
                    <AlertTitle className="text-red-800">Variance Detected</AlertTitle>
                    <AlertDescription className="text-red-700">
                      Amounts differ. Please review carefully before matching.
                    </AlertDescription>
                  </>
                )}
              </Alert>

            </div>
            <div className="p-6 border-t flex justify-between items-center">
              <div>
                {selectedTransaction[panelLHS]?.amount !== selectedTransaction[panelRHS]?.amount && (
                  <Alert className="border-red-200 bg-red-50 w-full">
                    <AlertCircle className="h-4 w-4 text-red-600" />
                    <AlertTitle className="text-red-800">Amount Mismatch</AlertTitle>
                    <AlertDescription className="text-red-700">
                      Cannot match: {panelLHS.toUpperCase()} amount (₹{selectedTransaction[panelLHS]?.amount?.toLocaleString()}) ≠ {panelRHS.toUpperCase()} amount (₹{selectedTransaction[panelRHS]?.amount?.toLocaleString()})
                    </AlertDescription>
                  </Alert>
                )}
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => dispatch({ type: 'CLOSE_DUAL_PANEL' })}>Cancel</Button>
                <Button
                  onClick={confirmForceMatch}
                  disabled={isMatching || !zeroDifferenceValid || panelLHS === panelRHS || selectedTransaction[panelLHS]?.amount !== selectedTransaction[panelRHS]?.amount}
                  title={selectedTransaction[panelLHS]?.amount !== selectedTransaction[panelRHS]?.amount ? 'Amounts must be equal to match' : ''}
                >
                  {isMatching ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                  Confirm Match
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
