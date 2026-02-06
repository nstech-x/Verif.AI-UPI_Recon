import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Badge } from "../components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Loader2, RotateCcw, AlertTriangle, CheckCircle2, RefreshCw, Zap, FolderOpen, BarChart3, Repeat } from "lucide-react";
import { useToast } from "../hooks/use-toast";
import { apiClient } from "../lib/api";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../components/ui/alert-dialog";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../components/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Input } from "../components/ui/input";

interface RunHistory {
  run_id: string;
  date: string;
  time: string;
  total_transactions: number;
  matched: number;
  unmatched: number;
  status: string;
}

interface RollbackHistory {
  rollback_id: string;
  level: string;
  timestamp: string;
  status: string;
  details: any;
}

interface AvailableCycles {
  status: string;
  run_id: string;
  available_cycles: string[];
  total_available: number;
  all_cycles: string[];
}

type RollbackLevel = "ttum" | "reports" | "recon" | "file" | "complete";

export default function Rollback() {
  const { toast } = useToast();

  // State for run history
  const [runHistory, setRunHistory] = useState<RunHistory[]>([]);
  const [loading, setLoading] = useState(true);

  // State for granular rollback
  const [selectedRun, setSelectedRun] = useState<string>("");
  const [rollbackLevel, setRollbackLevel] = useState<RollbackLevel>("complete");
  const [cycleId, setCycleId] = useState("");
  const [rollbackReason, setRollbackReason] = useState("");
  const [ttumDownloaded, setTtumDownloaded] = useState(false);

  // UI state
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [isRollingBack, setIsRollingBack] = useState(false);
  const [rollbackHistory, setRollbackHistory] = useState<RollbackHistory[]>([]);
  const [rollbackHistoryLoading, setRollbackHistoryLoading] = useState(false);
  const [availableCycles, setAvailableCycles] = useState<AvailableCycles | null>(null);
  const [cyclesLoading, setCyclesLoading] = useState(false);
  const [auditTrail, setAuditTrail] = useState<any[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);



  useEffect(() => {
    fetchRunHistory();
    fetchRollbackHistory();
  }, []);

  // Fetch available cycles when selected run changes
  useEffect(() => {
    if (selectedRun) {
      fetchAvailableCycles(selectedRun);
    } else {
      setAvailableCycles(null);
    }
  }, [selectedRun]);

  const fetchRunHistory = async () => {
    try {
      setLoading(true);

      // Fetch real historical data and summary
      const [historicalResponse, summaryResponse] = await Promise.all([
        apiClient.getHistoricalSummary(),
        apiClient.getSummary()
      ]);

      console.log('Historical data:', historicalResponse);
      console.log('Summary data:', summaryResponse);

      const runMap = new Map<string, RunHistory>();

      // Process historical data
      if (historicalResponse && Array.isArray(historicalResponse)) {
        historicalResponse.forEach((item: any) => {
          const runId = item.run_id || `RUN_${item.month?.replace('-', '') || 'DEMO'}`;
          if (!runMap.has(runId)) {
            runMap.set(runId, {
              run_id: runId,
              date: item.month || item.date || new Date().toISOString().split('T')[0],
              time: item.time || '12:00:00',
              total_transactions: item.allTxns || item.total_transactions || 0,
              matched: item.reconciled || item.matched || 0,
              unmatched: (item.allTxns || item.total_transactions || 0) - (item.reconciled || item.matched || 0),
              status: item.status || 'completed'
            });
          }
        });
      }

      // Add latest run from summary
      if (summaryResponse && summaryResponse.run_id && !runMap.has(summaryResponse.run_id)) {
        const latestRun: RunHistory = {
          run_id: summaryResponse.run_id,
          date: summaryResponse.generated_at ? new Date(summaryResponse.generated_at).toISOString().split('T')[0] : new Date().toISOString().split('T')[0],
          time: summaryResponse.generated_at ? new Date(summaryResponse.generated_at).toTimeString().split(' ')[0] : new Date().toTimeString().split(' ')[0],
          total_transactions: summaryResponse.totals?.count || summaryResponse.total_transactions || 0,
          matched: summaryResponse.matched?.count || 0,
          unmatched: summaryResponse.unmatched?.count || 0,
          status: summaryResponse.status || 'completed'
        };
        runMap.set(summaryResponse.run_id, latestRun);
      }

      const history = Array.from(runMap.values()).sort((a, b) =>
        new Date(b.date + ' ' + b.time).getTime() - new Date(a.date + ' ' + a.time).getTime()
      );

      setRunHistory(history);
    } catch (error) {
      console.error('Failed to fetch run history:', error);
      toast({
        title: "Error",
        description: "Failed to load run history. Please try again.",
        variant: "destructive"
      });
      setRunHistory([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchRollbackHistory = async () => {
    // DEMO MODE: Empty rollback history
    setRollbackHistoryLoading(true);
    setRollbackHistory([]);
    setRollbackHistoryLoading(false);
  };

  const fetchAvailableCycles = async (runId: string) => {
    try {
      setCyclesLoading(true);
      const response = await apiClient.getAvailableCycles(runId);
      console.log('Available cycles:', response);
      setAvailableCycles(response);
    } catch (error) {
      console.error('Failed to fetch available cycles:', error);
      // Fallback to default cycles
      setAvailableCycles({
        status: 'success',
        run_id: runId,
        available_cycles: ['1C', '2C', '3C', '4C', '5C', '6C', '7C', '8C', '9C', '10C'],
        total_available: 10,
        all_cycles: ['1C', '2C', '3C', '4C', '5C', '6C', '7C', '8C', '9C', '10C']
      });
    } finally {
      setCyclesLoading(false);
    }
  };

  const handleRollback = async () => {
    if (!selectedRun) {
      toast({
        title: "Error",
        description: "Please select a run",
        variant: "destructive"
      });
      return;
    }

    // Check TTUM guardrail
    if (rollbackLevel === "ttum" && ttumDownloaded) {
      toast({
        title: "Rollback Disabled",
        description: "Cannot rollback TTUM - Files have already been downloaded",
        variant: "destructive"
      });
      return;
    }

    try {
      setIsRollingBack(true);
      let result;
      const reason = rollbackReason || `User initiated ${rollbackLevel} rollback`;

      switch (rollbackLevel) {
        case "ttum":
          // TTUM rollback - only deletes TTUM reports
          result = await apiClient.rollbackAccounting(selectedRun, reason);
          break;
        case "reports":
          // Reports rollback - deletes whole report but not recon output
          result = await apiClient.rollbackMidRecon(selectedRun, reason);
          break;
        case "recon":
          // Recon rollback - deletes output + reports but not uploads
          result = await apiClient.rollbackMidRecon(selectedRun, reason);
          break;
        case "file":
          // File rollback - cycle-wise rollback with cycle selection
          if (!cycleId) {
            throw new Error("Cycle ID is required for file rollback");
          }
          result = await apiClient.rollbackCycleWise(selectedRun, cycleId);
          break;
        case "complete":
          // Complete rollback - deletes uploads + whole reports
          result = await apiClient.rollbackWholeProcess(selectedRun, reason);
          break;
        default:
          throw new Error("Invalid rollback level");
      }

      toast({
        title: "Success",
        description: result.message || `${rollbackLevel} rollback completed successfully`,
      });

      setShowConfirmDialog(false);
      resetForm();
      await Promise.all([fetchRunHistory(), fetchRollbackHistory(), selectedRun && fetchAuditTrail(selectedRun)]);
    } catch (error: any) {
      console.error("Rollback error:", error);
      toast({
        title: "Error",
        description: error.message || "Rollback failed. Please try again.",
        variant: "destructive"
      });
    } finally {
      setIsRollingBack(false);
    }
  };

  const fetchAuditTrail = async (runId: string) => {
    try {
      setAuditLoading(true);
      const response = await apiClient.getAuditTrail(runId);
      console.log('Audit trail:', response);
      setAuditTrail(response || []);
    } catch (error) {
      console.error('Failed to fetch audit trail:', error);
      setAuditTrail([]);
    } finally {
      setAuditLoading(false);
    }
  };

  // Fetch audit trail when selectedRun changes
  useEffect(() => {
    if (selectedRun) {
      fetchAuditTrail(selectedRun);
    }
  }, [selectedRun]);

  const resetForm = () => {
    setSelectedRun("");
    setCycleId("");
    setRollbackReason("");
  };

  const getRollbackLevelBadge = (level: string) => {
    const colors: Record<string, string> = {
      ttum: "bg-purple-500",
      reports: "bg-blue-500",
      recon: "bg-cyan-500",
      file: "bg-green-500",
      complete: "bg-red-500"
    };

    return (
      <Badge className={`${colors[level] || "bg-gray-500"} text-white`}>
        {level.toUpperCase()}
      </Badge>
    );
  };

  const getRollbackStatusBadge = (status: string) => {
    const variants: Record<string, any> = {
      'completed': { variant: 'default' as const, className: 'bg-green-500 text-white' },
      'in_progress': { variant: 'secondary' as const, className: 'bg-blue-500 text-white' },
      'failed': { variant: 'destructive' as const, className: 'bg-red-500 text-white' },
      'pending': { variant: 'outline' as const, className: 'bg-gray-500 text-white' }
    };

    const config = variants[status] || { variant: 'outline' as const, className: 'bg-gray-500 text-white' };

    return (
      <Badge variant={config.variant} className={config.className}>
        {status.replace('_', ' ').toUpperCase()}
      </Badge>
    );
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Granular Rollback Manager</h1>
          <p className="text-muted-foreground">Phase 3: Undo operations at any stage with full control</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => Promise.all([fetchRunHistory(), fetchRollbackHistory()])}
          disabled={loading || rollbackHistoryLoading}
          className="gap-2"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="rollback" className="w-full">
        <TabsList className="bg-muted/30">
          <TabsTrigger value="rollback" className="data-[state=active]:bg-brand-blue data-[state=active]:text-primary-foreground">
            <Zap className="w-4 h-4 mr-2" />
            Granular Rollback
          </TabsTrigger>
          <TabsTrigger value="history" className="data-[state=active]:bg-brand-blue data-[state=active]:text-primary-foreground">
            <RotateCcw className="w-4 h-4 mr-2" />
            Rollback History
          </TabsTrigger>
          <TabsTrigger value="runs" className="data-[state=active]:bg-brand-blue data-[state=active]:text-primary-foreground">
            <RefreshCw className="w-4 h-4 mr-2" />
            Run History
          </TabsTrigger>
        </TabsList>

        {/* ROLLBACK TAB */}
        <TabsContent value="rollback" className="space-y-6 mt-6">
          {/* Warning Alert */}
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Granular Rollback Operations</AlertTitle>
            <AlertDescription>
              Select the appropriate rollback level for your use case. Each level targets specific stages of the reconciliation process.
            </AlertDescription>
          </Alert>

          {/* Rollback Form */}
          <Card className="shadow-lg">
            <CardHeader>
              <CardTitle>Configure Rollback</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Run Selection */}
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700">Select Run</label>
                <Select value={selectedRun} onValueChange={setSelectedRun}>
                  <SelectTrigger className="border-slate-300">
                    <SelectValue placeholder="Select a reconciliation run" />
                  </SelectTrigger>
                  <SelectContent>
                    {runHistory.map((run, index) => (
                      <SelectItem key={`${run.run_id}-${index}`} value={run.run_id}>
                        {run.run_id} - {run.date} {run.time} ({run.matched}/{run.total_transactions} matched)
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Rollback Level Selection - 5 Levels */}
              <div className="space-y-3">
                <label className="text-sm font-semibold text-slate-700">Rollback Level</label>
                <div className="grid grid-cols-5 gap-2">
                  {[
                    { level: 'file' as RollbackLevel, icon: '📁', label: 'File', color: 'green' },
                    { level: 'recon' as RollbackLevel, icon: '🔄', label: 'Recon', color: 'cyan' },
                    { level: 'reports' as RollbackLevel, icon: '📊', label: 'Reports', color: 'blue' },
                    { level: 'ttum' as RollbackLevel, icon: '📄', label: 'TTUM', color: 'purple' },
                    { level: 'complete' as RollbackLevel, icon: '💣', label: 'Complete', color: 'red' },
                  ].map(({ level, icon, label, color }) => {
                    const colorMap: Record<string, { border: string; bg: string; hover: string }> = {
                      purple: { border: 'border-purple-500', bg: 'bg-purple-50', hover: 'hover:border-purple-300 hover:bg-purple-50' },
                      blue: { border: 'border-blue-500', bg: 'bg-blue-50', hover: 'hover:border-blue-300 hover:bg-blue-50' },
                      cyan: { border: 'border-cyan-500', bg: 'bg-cyan-50', hover: 'hover:border-cyan-300 hover:bg-cyan-50' },
                      green: { border: 'border-green-500', bg: 'bg-green-50', hover: 'hover:border-green-300 hover:bg-green-50' },
                      red: { border: 'border-red-500', bg: 'bg-red-50', hover: 'hover:border-red-300 hover:bg-red-50' },
                    };
                    const styles = colorMap[color];
                    return (
                      <button
                        key={level}
                        onClick={() => setRollbackLevel(level)}
                        className={`h-24 flex flex-col items-center justify-center rounded-lg border-2 transition-all duration-200 text-xs ${
                          rollbackLevel === level
                            ? `${styles.border} ${styles.bg} shadow-md`
                            : `border-slate-200 bg-white ${styles.hover}`
                        }`}
                      >
                        <div className="text-2xl mb-1">{icon}</div>
                        <div className="font-semibold text-slate-800">{label}</div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Cycle Selection for File Rollback */}
              {rollbackLevel === 'file' && (
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-slate-700">Select Cycle for File Rollback</label>
                  <Select value={cycleId} onValueChange={setCycleId}>
                    <SelectTrigger className="border-slate-300">
                      <SelectValue placeholder="Select a cycle (1C, 2C, ..., 10C)" />
                    </SelectTrigger>
                    <SelectContent>
                      {cyclesLoading ? (
                        <div className="flex items-center justify-center py-2">
                          <Loader2 className="w-4 h-4 animate-spin mr-2" />
                          Loading cycles...
                        </div>
                      ) : availableCycles?.available_cycles?.length ? (
                        availableCycles.available_cycles.map((cycle) => (
                          <SelectItem key={cycle} value={cycle}>
                            Cycle {cycle}
                          </SelectItem>
                        ))
                      ) : (
                        <>
                          <SelectItem value="1C">Cycle 1C</SelectItem>
                          <SelectItem value="2C">Cycle 2C</SelectItem>
                          <SelectItem value="3C">Cycle 3C</SelectItem>
                          <SelectItem value="4C">Cycle 4C</SelectItem>
                          <SelectItem value="5C">Cycle 5C</SelectItem>
                          <SelectItem value="6C">Cycle 6C</SelectItem>
                          <SelectItem value="7C">Cycle 7C</SelectItem>
                          <SelectItem value="8C">Cycle 8C</SelectItem>
                          <SelectItem value="9C">Cycle 9C</SelectItem>
                          <SelectItem value="10C">Cycle 10C</SelectItem>
                        </>
                      )}
                    </SelectContent>
                  </Select>
                  {rollbackLevel === 'file' && !cycleId && (
                    <p className="text-xs text-red-500 mt-1">Please select a cycle for file rollback</p>
                  )}
                </div>
              )}

              {/* TTUM Guardrail */}
              {rollbackLevel === 'ttum' && ttumDownloaded && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>Rollback Disabled</AlertTitle>
                  <AlertDescription>
                    Cannot rollback TTUM - Files have already been downloaded. This is a safety measure to prevent data inconsistency.
                  </AlertDescription>
                </Alert>
              )}

              {/* Rollback Reason */}
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-700">Reason/Comments (Optional)</label>
                <textarea
                  value={rollbackReason}
                  onChange={(e) => setRollbackReason(e.target.value)}
                  placeholder="Describe why you're initiating this rollback"
                  className="w-full p-3 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue"
                  rows={3}
                />
              </div>

              {/* Submit Button */}
              <Button
                size="lg"
                className="w-full bg-brand-blue hover:bg-brand-mid"
                onClick={() => setShowConfirmDialog(true)}
                disabled={!selectedRun || isRollingBack || (rollbackLevel === 'file' && !cycleId)}
              >
                {isRollingBack ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <RotateCcw className="w-4 h-4 mr-2" />
                    Initiate {rollbackLevel.toUpperCase()} Rollback
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Audit Trail Section */}
          {selectedRun && (
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle>Audit Trail for {selectedRun}</CardTitle>
              </CardHeader>
              <CardContent>
                {auditLoading ? (
                  <div className="flex justify-center py-8">
                    <Loader2 className="w-8 h-8 animate-spin text-brand-blue" />
                  </div>
                ) : auditTrail.length === 0 ? (
                  <div className="text-center py-8">
                    <p className="text-muted-foreground">No audit entries found for this run</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Timestamp</TableHead>
                          <TableHead>Action</TableHead>
                          <TableHead>User</TableHead>
                          <TableHead>Details</TableHead>
                          <TableHead>Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {auditTrail.map((entry, idx) => (
                          <TableRow key={idx}>
                            <TableCell className="text-sm">{new Date(entry.timestamp).toLocaleString()}</TableCell>
                            <TableCell className="font-medium text-sm">{entry.action}</TableCell>
                            <TableCell className="text-sm">{entry.user || 'System'}</TableCell>
                            <TableCell className="text-sm text-muted-foreground">{entry.details}</TableCell>
                            <TableCell>
                              {entry.status === 'success' ? (
                                <Badge className="bg-green-500 text-white">Success</Badge>
                              ) : entry.status === 'failed' ? (
                                <Badge className="bg-red-500 text-white">Failed</Badge>
                              ) : (
                                <Badge className="bg-gray-500 text-white">Pending</Badge>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Level Descriptions */}
          <div className="grid grid-cols-1 gap-4">
            <Card className="border-green-200 bg-green-50">
              <CardContent className="pt-6">
                <h3 className="font-semibold text-green-900 mb-2">File Rollback</h3>
                <p className="text-sm text-green-800">Undo file upload and validation, returning to pre-upload state.</p>
              </CardContent>
            </Card>
            <Card className="border-cyan-200 bg-cyan-50">
              <CardContent className="pt-6">
                <h3 className="font-semibold text-cyan-900 mb-2">Recon Rollback</h3>
                <p className="text-sm text-cyan-800">Undo reconciliation process, reverting to uploaded file state.</p>
              </CardContent>
            </Card>
            <Card className="border-blue-200 bg-blue-50">
              <CardContent className="pt-6">
                <h3 className="font-semibold text-blue-900 mb-2">Reports Rollback</h3>
                <p className="text-sm text-blue-800">Undo all report generation (Matched, Unmatched, etc.) while preserving reconciliation data.</p>
              </CardContent>
            </Card>
            <Card className="border-purple-200 bg-purple-50">
              <CardContent className="pt-6">
                <h3 className="font-semibold text-purple-900 mb-2">TTUM Rollback</h3>
                <p className="text-sm text-purple-800">Undo TTUM report generation. **Guardrail:** Cannot rollback if TTUM files have been downloaded.</p>
              </CardContent>
            </Card>
            <Card className="border-red-200 bg-red-50">
              <CardContent className="pt-6">
                <h3 className="font-semibold text-red-900 mb-2">Complete Rollback</h3>
                <p className="text-sm text-red-800"><strong>WARNING:</strong> Full reset to initial state. All operations, files, and data will be deleted.</p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* HISTORY TAB */}
        <TabsContent value="history" className="space-y-6 mt-6">
          <Card className="shadow-lg">
            <CardHeader>
              <CardTitle>Rollback Operations History</CardTitle>
            </CardHeader>
            <CardContent>
              {rollbackHistoryLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-8 h-8 animate-spin text-brand-blue" />
                </div>
              ) : rollbackHistory.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-muted-foreground">No rollback operations found</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Rollback ID</TableHead>
                        <TableHead>Level</TableHead>
                        <TableHead>Run ID</TableHead>
                        <TableHead>Timestamp</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rollbackHistory.map((record) => (
                        <TableRow key={record.rollback_id}>
                          <TableCell className="font-mono text-xs">{record.rollback_id}</TableCell>
                          <TableCell>{getRollbackLevelBadge(record.level)}</TableCell>
                          <TableCell className="font-mono font-medium">{record.details.run_id || record.level}</TableCell>
                          <TableCell className="text-sm">{new Date(record.timestamp).toLocaleString()}</TableCell>
                          <TableCell>{getRollbackStatusBadge(record.status)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* RUNS TAB */}
        <TabsContent value="runs" className="space-y-6 mt-6">
          <Card className="shadow-lg">
            <CardHeader>
              <CardTitle>Reconciliation Run History</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-8 h-8 animate-spin text-brand-blue" />
                </div>
              ) : runHistory.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-muted-foreground">No reconciliation runs found</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Run ID</TableHead>
                        <TableHead>Date</TableHead>
                        <TableHead>Time</TableHead>
                        <TableHead className="text-right">Total</TableHead>
                        <TableHead className="text-right">Matched</TableHead>
                        <TableHead className="text-right">Unmatched</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {runHistory.map((run, index) => (
                        <TableRow key={`${run.run_id}-${index}`}>
                          <TableCell className="font-mono font-medium">{run.run_id}</TableCell>
                          <TableCell>{run.date}</TableCell>
                          <TableCell>{run.time}</TableCell>
                          <TableCell className="text-right font-semibold">
                            {run.total_transactions.toLocaleString()}
                          </TableCell>
                          <TableCell className="text-right text-green-600 font-semibold">
                            {run.matched.toLocaleString()}
                          </TableCell>
                          <TableCell className="text-right text-red-600 font-semibold">
                            {run.unmatched.toLocaleString()}
                          </TableCell>
                          <TableCell>
                            <Badge className="bg-green-500 text-white">
                              {run.status.toUpperCase()}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Confirmation Dialog */}
      <AlertDialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-orange-600" />
              Confirm {rollbackLevel.replace('_', ' ').toUpperCase()} Rollback
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  Are you sure you want to perform a <strong>{rollbackLevel.replace('_', ' ')}</strong> rollback on <strong>{selectedRun}</strong>?
                </p>
                {rollbackLevel === "complete" && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                    <p className="text-sm text-red-800">
                      <strong>WARNING:</strong> This will completely reset the entire reconciliation process for this run, including all matched transactions, vouchers, and processed data.
                    </p>
                  </div>
                )}
                {rollbackLevel === "file" && (
                  <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
                    <p className="text-sm text-purple-800">
                      Cycle <strong>{cycleId}</strong> transactions will be restored to unmatched state for reprocessing.
                    </p>
                  </div>
                )}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isRollingBack}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRollback}
              disabled={isRollingBack}
              className="bg-orange-600 hover:bg-orange-700"
            >
              {isRollingBack ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Rolling Back...
                </>
              ) : (
                <>
                  <RotateCcw className="w-4 h-4 mr-2" />
                  Confirm Rollback
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
