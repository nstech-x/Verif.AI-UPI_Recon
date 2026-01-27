import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Loader2, Download, X, RefreshCw } from "lucide-react";
import { apiClient } from "../lib/api";
import { useToast } from "../hooks/use-toast";
import CycleSelector from "../components/CycleSelector";
import DirectionSelector from "../components/DirectionSelector";
import { useDate } from "../contexts/DateContext";
import { exportToCSV } from "../lib/utils";
import { generateDemoHangingTransactions, generateDemoUnmatchedTransactions } from "../lib/demoData";

export default function Unmatched() {
  const { toast } = useToast();
  const { dateFrom, dateTo, setDateFrom, setDateTo } = useDate();
  const [unmatchedNPCI, setUnmatchedNPCI] = useState<any[]>([]);
  const [unmatchedCBS, setUnmatchedCBS] = useState<any[]>([]);
  const [unmatchedSWITCH, setUnmatchedSWITCH] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(new Date());
  const [searchTerm, setSearchTerm] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [amountFrom, setAmountFrom] = useState("");
  const [amountTo, setAmountTo] = useState("");
  const [selectedCycle, setSelectedCycle] = useState("all");
  const [selectedDirection, setSelectedDirection] = useState("all");

  const fetchUnmatchedData = async () => {
    try {
      setLoading(true);
      const response = await apiClient.getLatestUnmatched();
      console.log('API Response:', response);

      // Transform API response to expected format
      const transformedData = transformReportToUnmatched(response.unmatched || [], 'upi_array');

      setUnmatchedNPCI(transformedData.npci);
      setUnmatchedCBS(transformedData.cbs);
      setUnmatchedSWITCH(transformedData.switch);
      setLastRefresh(new Date());
      console.log(`Real data loaded - NPCI: ${transformedData.npci.length}, CBS: ${transformedData.cbs.length}, SWITCH: ${transformedData.switch.length}`);
    } catch (error) {
      console.error('Failed to fetch unmatched data:', error);
      toast({
        title: "Error",
        description: "Failed to load unmatched transactions. Please try again.",
        variant: "destructive"
      });
      // Fallback to empty arrays
      setUnmatchedNPCI([]);
      setUnmatchedCBS([]);
      setUnmatchedSWITCH([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Initial fetch
    fetchUnmatchedData();

    // Set up auto-refresh every 30 seconds for real-time updates
    const refreshInterval = setInterval(() => {
      fetchUnmatchedData();
    }, 30000);

    // Cleanup interval on unmount
    return () => clearInterval(refreshInterval);
  }, []);

  const transformReportToUnmatched = (data: any, format: string = 'legacy') => {
    console.log("Transforming data:", data, "format:", format);
    const npci: any[] = [];
    const cbs: any[] = [];
    const switch_: any[] = [];

    if (!data || (Array.isArray(data) && data.length === 0)) {
      console.warn("No data provided for unmatched transformation");
      return { npci, cbs, switch: switch_ };
    }

    // Handle UPI array format (new format from backend)
    if (format === 'upi_array' && Array.isArray(data)) {
      console.log(`Processing ${data.length} exceptions in UPI array format`);
      
    data.forEach((exc: any, index: number) => {
        if (!exc || typeof exc !== 'object') {
          console.warn(`Skipping invalid exception at index ${index}:`, exc);
          return;
        }

        // Log first few records to see available fields
        if (index < 3) {
          console.log(`Sample transaction ${index}:`, exc);
          console.log(`Available fields:`, Object.keys(exc));
        }

        // Validate required fields - RRN must be present
        const rrn = exc.rrn || exc.RRN;
        if (!rrn || rrn === 'unknown' || rrn === '') {
          console.warn(`Skipping exception with invalid RRN at index ${index}:`, exc);
          return;
        }

        // Check if RRN field actually contains a transaction ID (starts with TXN)
        let actualRrn = rrn;
        let actualTxnId = exc.reference || exc.UPI_Tran_ID || exc.upi_tran_id || 'N/A';
        
        // If RRN looks like a transaction ID (TXN prefix), swap them
        if (rrn.startsWith('TXN') || rrn.startsWith('txn')) {
          actualTxnId = rrn; // The "RRN" field is actually the transaction ID
          // Try to find actual RRN in other fields
          actualRrn = exc.RRN || exc.actual_rrn || exc.retrieval_reference_number || 
                     exc.reference_number || exc.upi_rrn || 'N/A';
        }

        const transaction = {
          source: exc.source || 'NPCI',
          rrn: actualRrn,
          upiTransactionId: actualTxnId,
          drCr: exc.debit_credit || exc.dr_cr || 'Dr',
          amount: parseFloat(String(exc.amount || 0)) || 0,
          amountFormatted: `₹${(parseFloat(String(exc.amount || 0)) || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
          tranDate: exc.date || exc.tran_date || new Date().toLocaleDateString(),
          time: exc.time || '',
          rc: exc.rc || '00',
          type: exc.type || exc.tran_type || 'UPI',
          exceptionType: exc.exception_type || 'UNMATCHED',
          ttumRequired: exc.ttum_required || false,
          direction: exc.direction || 'UNKNOWN',
          reference: exc.reference || ''
        };

        // Route to appropriate list based on source
        const source = (exc.source || 'NPCI').toUpperCase();
        if (source === 'NPCI') {
          npci.push(transaction);
        } else if (source === 'CBS') {
          cbs.push(transaction);
        } else if (source === 'SWITCH') {
          switch_.push(transaction);
        } else {
          // Unknown source - add to NPCI by default
          npci.push(transaction);
        }
      });

      console.log(`Transformed UPI array format - NPCI: ${npci.length}, CBS: ${cbs.length}, SWITCH: ${switch_.length}`);
      return { npci, cbs, switch: switch_ };
    }
    // Handle legacy object format
    else if (typeof data === 'object' && !Array.isArray(data)) {
      // Convert object to array format
      const records = Object.entries(data).map(([rrn, record]) => ({
        rrn,
        ...(record && typeof record === 'object' ? record : {})
      }));

      records.forEach((record: any) => {
        if (!record) return;

        const rrn = record.rrn || record.RRN || 'unknown';

        // Extract data from each source - handle multiple naming conventions
        const cbs_data = record.cbs || record.CBS || record.gl;
        const switch_data = record.switch || record.SWITCH;
        const npci_data = record.npci || record.NPCI;

        // Helper to create transaction object
        const createTransaction = (sourceData: any, sourceName: string) => {
          if (!sourceData) return null;

          const amount = parseFloat(sourceData.amount) || 0;
          const drCr = sourceData.dr_cr || sourceData.debit_credit || sourceData.debit || "Dr";
          
          // Determine direction
          let direction = 'UNKNOWN';
          if (drCr) {
            const drCrUpper = String(drCr).toUpperCase();
            direction = drCrUpper.startsWith('C') ? 'INWARD' : drCrUpper.startsWith('D') ? 'OUTWARD' : 'UNKNOWN';
          }

          return {
            source: sourceName,
            rrn: rrn,
            upiTransactionId: sourceData.reference || sourceData.upi_tran_id || sourceData.UPI_Tran_ID || sourceData.transaction_id || 'N/A',
            drCr: drCr,
            amount: amount,
            amountFormatted: `₹${amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
            tranDate: sourceData.date || sourceData.tran_date || sourceData.transaction_date || new Date().toLocaleDateString(),
            rc: sourceData.rc || sourceData.response_code || "00",
            type: sourceData.tran_type || sourceData.type || "UPI",
            direction: direction
          };
        };

        // Determine which system is missing
        const hasCBS = cbs_data !== null && cbs_data !== undefined;
        const hasSwitch = switch_data !== null && switch_data !== undefined;
        const hasNPCI = npci_data !== null && npci_data !== undefined;

        // Add to NPCI list if NPCI data exists but CBS is missing
        if (hasNPCI && !hasCBS) {
          const transaction = createTransaction(npci_data, "NPCI");
          if (transaction) npci.push(transaction);
        }

        // Add to CBS list if CBS data exists but NPCI is missing
        if (hasCBS && !hasNPCI) {
          const transaction = createTransaction(cbs_data, "CBS");
          if (transaction) cbs.push(transaction);
        }

        // Also add if it's a mismatch or partial match
        if (record.status === 'PARTIAL_MATCH' || record.status === 'MISMATCH' || record.status === 'HANGING' || record.status === 'PARTIAL_MISMATCH') {
          if (hasNPCI) {
            const transaction = createTransaction(npci_data, "NPCI");
            if (transaction && !npci.some(t => t.rrn === rrn)) npci.push(transaction);
          }
          if (hasCBS) {
            const transaction = createTransaction(cbs_data, "CBS");
            if (transaction && !cbs.some(t => t.rrn === rrn)) cbs.push(transaction);
          }
        }
      });

      console.log(`Transformed legacy format - NPCI: ${npci.length}, CBS: ${cbs.length}, SWITCH: ${switch_.length}`);
      console.log("Transformed:", { npci, cbs, switch: switch_ });
      return { npci, cbs, switch: switch_ };
    }
    else {
      console.warn("Invalid data format for unmatched transformation:", data);
      return { npci, cbs, switch: switch_ };
    }
  };

  // Helper function to parse and format dates for comparison
  const parseDate = (dateString: string): Date | null => {
    if (!dateString) return null;
    // Try parsing DD/MM/YYYY format
    const parts = dateString.split('/');
    if (parts.length === 3) {
      const date = new Date(`${parts[2]}-${parts[1]}-${parts[0]}`);
      return isNaN(date.getTime()) ? null : date;
    }
    // Try YYYY-MM-DD format
    const date = new Date(dateString);
    return isNaN(date.getTime()) ? null : date;
  };

  // Helper function to check if transaction matches all filters
  const matchesFilters = (row: any): boolean => {
    // RRN search - search in both RRN and Transaction ID fields
    if (searchTerm) {
      const searchLower = searchTerm.toUpperCase();
      const rrnMatch = row.rrn && row.rrn.toUpperCase().includes(searchLower);
      const txnIdMatch = row.upiTransactionId && row.upiTransactionId.toUpperCase().includes(searchLower);
      if (!rrnMatch && !txnIdMatch) {
        return false;
      }
    }

    // Account Number search (mock - in real system would search actual account field)
    if (accountNumber && (!row.upiTransactionId || !row.upiTransactionId.toUpperCase().includes(accountNumber.toUpperCase()))) {
      return false;
    }

    // Cycle filter - for now, we'll filter based on RRN pattern or skip if no cycle info
    // This can be enhanced when cycle info is available in the data
    if (selectedCycle !== "all") {
      // If cycle info is not available in the data, we'll allow all transactions
      // This can be improved when backend provides cycle information
      // For now, we'll skip cycle filtering
    }

    // Direction filter
    if (selectedDirection !== "all") {
      const rowDirection = row.direction || (row.drCr?.startsWith('C') ? 'INWARD' : row.drCr?.startsWith('D') ? 'OUTWARD' : 'UNKNOWN');
      if (rowDirection.toUpperCase() !== selectedDirection.toUpperCase()) {
        return false;
      }
    }

    // Date range filter
    if (dateFrom || dateTo) {
      const tranDate = parseDate(row.tranDate);
      const fromDate = dateFrom ? new Date(dateFrom) : null;
      const toDate = dateTo ? new Date(dateTo) : null;

      if (tranDate) {
        if (fromDate && tranDate < fromDate) return false;
        if (toDate && tranDate > toDate) return false;
      }
    }

    // Transaction type filter
    if (typeFilter !== "all" && row.type.toLowerCase() !== typeFilter.toLowerCase()) {
      return false;
    }

    // Amount range filter
    if (amountFrom && row.amount < parseFloat(amountFrom)) {
      return false;
    }
    if (amountTo && row.amount > parseFloat(amountTo)) {
      return false;
    }

    return true;
  };

  const handleClearFilters = () => {
    setSearchTerm("");
    setAccountNumber("");
    setDateFrom("");
    setDateTo("");
    setTypeFilter("all");
    setAmountFrom("");
    setAmountTo("");
    setSelectedCycle("all");
    setSelectedDirection("all");
    toast({
      title: "Filters cleared",
      description: "All filters have been reset"
    });
  };

  const handleExportCSV = (data: any[], filename: string) => {
    const csvData = data.map(row => ({
      Source: row.source,
      RRN: row.rrn,
      "UPI Transaction ID": row.upiTransactionId,
      "Dr/Cr": row.drCr,
      Amount: row.amount,
      "Transaction Date": row.tranDate,
      RC: row.rc,
      Type: row.type
    }));
    exportToCSV(csvData, filename);
    toast({
      title: "Export successful",
      description: `${filename} has been downloaded`
    });
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Unmatched Dashboard</h1>
          <p className="text-muted-foreground">View and manage unmatched transactions with advanced filtering</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">
            Last updated: {lastRefresh.toLocaleTimeString()}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchUnmatchedData}
            disabled={loading}
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card className="shadow-lg">
        <CardContent className="pt-6">
          <div className="space-y-4">
            {/* First row: Cycle and Direction */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Cycle</label>
                <CycleSelector value={selectedCycle} onValueChange={setSelectedCycle} />
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">Direction</label>
                <DirectionSelector value={selectedDirection} onValueChange={setSelectedDirection} />
              </div>
            </div>

            {/* Second row: RRN & A/C Number search */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Search by RRN</label>
                <Input
                  placeholder="Enter RRN..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">Search by A/C Number</label>
                <Input
                  placeholder="Enter Account Number..."
                  value={accountNumber}
                  onChange={(e) => setAccountNumber(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">Date From</label>
                <Input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">Date To</label>
                <Input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                />
              </div>
            </div>

            {/* Third row: Transaction type and amount range */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Transaction Type</label>
                <Select value={typeFilter} onValueChange={setTypeFilter}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="upi">UPI</SelectItem>
                    <SelectItem value="p2p">P2P</SelectItem>
                    <SelectItem value="p2m">P2M</SelectItem>
                    <SelectItem value="neft">NEFT</SelectItem>
                    <SelectItem value="imps">IMPS</SelectItem>
                    <SelectItem value="rtgs">RTGS</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">Amount From (₹)</label>
                <Input
                  type="number"
                  placeholder="0"
                  value={amountFrom}
                  onChange={(e) => setAmountFrom(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">Amount To (₹)</label>
                <Input
                  type="number"
                  placeholder="999999999"
                  value={amountTo}
                  onChange={(e) => setAmountTo(e.target.value)}
                />
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex gap-2 justify-end pt-2">
              <Button 
                variant="outline"
                className="rounded-full"
                onClick={handleClearFilters}
              >
                Clear All
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tabs for NPCI, CBS, and SWITCH */}
      <Tabs defaultValue="npci" className="w-full">
        <TabsList className="bg-muted/30">
          <TabsTrigger
            value="npci"
            className="data-[state=active]:bg-brand-blue data-[state=active]:text-primary-foreground"
          >
            NPCI Unmatched ({unmatchedNPCI.filter(matchesFilters).length}/{unmatchedNPCI.length})
          </TabsTrigger>
          <TabsTrigger
            value="cbs"
            className="data-[state=active]:bg-brand-blue data-[state=active]:text-primary-foreground"
          >
            CBS Unmatched ({unmatchedCBS.filter(matchesFilters).length}/{unmatchedCBS.length})
          </TabsTrigger>
          <TabsTrigger
            value="switch"
            className="data-[state=active]:bg-brand-blue data-[state=active]:text-primary-foreground"
          >
            SWITCH Unmatched ({unmatchedSWITCH.filter(matchesFilters).length}/{unmatchedSWITCH.length})
          </TabsTrigger>
        </TabsList>

        {/* NPCI Unmatched */}
        <TabsContent value="npci">
          <Card className="shadow-lg">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>NPCI Unmatched Transactions</CardTitle>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => handleExportCSV(unmatchedNPCI.filter(matchesFilters), 'npci_unmatched.csv')}
                  disabled={unmatchedNPCI.filter(matchesFilters).length === 0}
                >
                  <Download className="w-4 h-4" />
                  Export CSV
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-8 h-8 animate-spin text-brand-blue" />
                </div>
              ) : (
                <>
                  {/* Debug info */}
                  {unmatchedNPCI.length > 0 && (
                    <div className="mb-2 text-xs text-muted-foreground">
                      Showing {unmatchedNPCI.filter(matchesFilters).length} of {unmatchedNPCI.length} transactions
                    </div>
                  )}
                  
                  {unmatchedNPCI.filter(matchesFilters).length === 0 ? (
                    <p className="text-center text-muted-foreground py-8">
                      {unmatchedNPCI.length === 0 ? 'No unmatched NPCI transactions found' : 'No transactions match the current filters'}
                    </p>
                  ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Source</TableHead>
                      <TableHead>RRN</TableHead>
                      <TableHead>UPI Transaction ID</TableHead>
                      <TableHead>Dr/Cr</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Tran Date</TableHead>
                      <TableHead>RC</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {unmatchedNPCI
                      .filter(matchesFilters)
                      .map((row, idx) => (
                        <TableRow key={idx}>
                          <TableCell className="font-medium">{row.source}</TableCell>
                          <TableCell className="font-mono text-xs">
                            {row.rrn === 'N/A' ? (
                              <span className="text-orange-600" title="RRN not available - using Transaction ID">
                                {row.upiTransactionId}
                              </span>
                            ) : (
                              row.rrn
                            )}
                          </TableCell>
                          <TableCell className="font-mono text-xs">{row.upiTransactionId}</TableCell>
                          <TableCell>
                            <span className={row.drCr === "Dr" ? "text-red-600" : "text-green-600"}>
                              {row.drCr}
                            </span>
                          </TableCell>
                          <TableCell className="font-semibold">{row.amountFormatted}</TableCell>
                          <TableCell>{row.tranDate}</TableCell>
                          <TableCell>{row.rc}</TableCell>
                          <TableCell>{row.type}</TableCell>
                          <TableCell>
                            <Button variant="outline" size="sm" className="rounded-full">
                              Match
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* CBS Unmatched */}
        <TabsContent value="cbs">
          <Card className="shadow-lg">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>CBS Unmatched Transactions</CardTitle>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => handleExportCSV(unmatchedCBS.filter(matchesFilters), 'cbs_unmatched.csv')}
                  disabled={unmatchedCBS.filter(matchesFilters).length === 0}
                >
                  <Download className="w-4 h-4" />
                  Export CSV
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-8 h-8 animate-spin text-brand-blue" />
                </div>
              ) : (
                <>
                  {/* Debug info */}
                  {unmatchedCBS.length > 0 && (
                    <div className="mb-2 text-xs text-muted-foreground">
                      Showing {unmatchedCBS.filter(matchesFilters).length} of {unmatchedCBS.length} transactions
                    </div>
                  )}
                  
                  {unmatchedCBS.filter(matchesFilters).length === 0 ? (
                    <p className="text-center text-muted-foreground py-8">
                      {unmatchedCBS.length === 0 ? 'No unmatched CBS transactions found' : 'No transactions match the current filters'}
                    </p>
                  ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Source</TableHead>
                      <TableHead>RRN</TableHead>
                      <TableHead>UPI Transaction ID</TableHead>
                      <TableHead>Dr/Cr</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Tran Date</TableHead>
                      <TableHead>RC</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {unmatchedCBS
                      .filter(matchesFilters)
                      .map((row, idx) => (
                        <TableRow key={idx}>
                          <TableCell className="font-medium">{row.source}</TableCell>
                          <TableCell className="font-mono text-xs">
                            {row.rrn === 'N/A' ? (
                              <span className="text-orange-600" title="RRN not available - using Transaction ID">
                                {row.upiTransactionId}
                              </span>
                            ) : (
                              row.rrn
                            )}
                          </TableCell>
                          <TableCell className="font-mono text-xs">{row.upiTransactionId}</TableCell>
                          <TableCell>
                            <span className={row.drCr === "Dr" ? "text-red-600" : "text-green-600"}>
                              {row.drCr}
                            </span>
                          </TableCell>
                          <TableCell className="font-semibold">{row.amountFormatted}</TableCell>
                          <TableCell>{row.tranDate}</TableCell>
                          <TableCell>{row.rc}</TableCell>
                          <TableCell>{row.type}</TableCell>
                          <TableCell>
                            <Button variant="outline" size="sm" className="rounded-full">
                              Match
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* SWITCH Unmatched */}
        <TabsContent value="switch">
          <Card className="shadow-lg">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>SWITCH Unmatched Transactions</CardTitle>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => handleExportCSV(unmatchedSWITCH.filter(matchesFilters), 'switch_unmatched.csv')}
                  disabled={unmatchedSWITCH.filter(matchesFilters).length === 0}
                >
                  <Download className="w-4 h-4" />
                  Export CSV
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-8 h-8 animate-spin text-brand-blue" />
                </div>
              ) : (
                <>
                  {/* Debug info */}
                  {unmatchedSWITCH.length > 0 && (
                    <div className="mb-2 text-xs text-muted-foreground">
                      Showing {unmatchedSWITCH.filter(matchesFilters).length} of {unmatchedSWITCH.length} transactions
                    </div>
                  )}
                  
                  {unmatchedSWITCH.filter(matchesFilters).length === 0 ? (
                    <p className="text-center text-muted-foreground py-8">
                      {unmatchedSWITCH.length === 0 ? 'No unmatched SWITCH transactions found' : 'No transactions match the current filters'}
                    </p>
                  ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Source</TableHead>
                      <TableHead>RRN</TableHead>
                      <TableHead>UPI Transaction ID</TableHead>
                      <TableHead>Dr/Cr</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Tran Date</TableHead>
                      <TableHead>RC</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {unmatchedSWITCH
                      .filter(matchesFilters)
                      .map((row, idx) => (
                        <TableRow key={idx}>
                          <TableCell className="font-medium">{row.source}</TableCell>
                          <TableCell className="font-mono text-xs">
                            {row.rrn === 'N/A' ? (
                              <span className="text-orange-600" title="RRN not available - using Transaction ID">
                                {row.upiTransactionId}
                              </span>
                            ) : (
                              row.rrn
                            )}
                          </TableCell>
                          <TableCell className="font-mono text-xs">{row.upiTransactionId}</TableCell>
                          <TableCell>
                            <span className={row.drCr === "Dr" ? "text-red-600" : "text-green-600"}>
                              {row.drCr}
                            </span>
                          </TableCell>
                          <TableCell className="font-semibold">{row.amountFormatted}</TableCell>
                          <TableCell>{row.tranDate}</TableCell>
                          <TableCell>{row.rc}</TableCell>
                          <TableCell>{row.type}</TableCell>
                          <TableCell>
                            <Button variant="outline" size="sm" className="rounded-full">
                              Match
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
