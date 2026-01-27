import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Loader2, CheckCircle2, AlertCircle, TrendingUp, RefreshCw, FileText, AlertTriangle } from "lucide-react";
import { useToast } from "../hooks/use-toast";
import { apiClient } from "../lib/api";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../components/ui/alert";

interface GLAccount {
  account_code: string;
  account_name: string;
  opening_balance: number;
  closing_balance: number;
  book_balance: number;
  variance: number;
  variance_abs: number;
  reconciled: boolean;
}

interface VarianceBridge {
  bridge_id: string;
  category: string;
  description: string;
  amount: number;
  justification: string;
  aging_days: number;
  priority: string;
  resolved: boolean;
}

interface ProofingReport {
  report_id: string;
  run_id: string;
  report_date: string;
  summary: {
    total_accounts: number;
    reconciled_accounts: number;
    unreconciled_accounts: number;
    total_variance: number;
    total_variance_abs: number;
    total_bridged: number;
    bridging_coverage_percent: number;
    remaining_variance: number;
    fully_reconciled: boolean;
  };
  gl_accounts: GLAccount[];
  variance_bridges: VarianceBridge[];
}

export default function GLProofing() {
  const { toast } = useToast();
  const [reports, setReports] = useState<ProofingReport[]>([]);
  const [selectedReport, setSelectedReport] = useState<ProofingReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("summary");

  useEffect(() => {
    fetchReports();
  }, []);

  const fetchReports = async () => {
    try {
      setLoading(true);
      const response = await apiClient.getAllProofingReports();
      setReports(response.reports || []);
      if (response.reports && response.reports.length > 0) {
        setSelectedReport(response.reports[0]);
      }
    } catch (error) {
      console.error("Error fetching GL proofing reports:", error);
      toast({
        title: "Error",
        description: "Failed to load GL proofing reports",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "CRITICAL":
        return "bg-red-500 text-white";
      case "HIGH":
        return "bg-orange-500 text-white";
      case "MEDIUM":
        return "bg-yellow-500 text-white";
      default:
        return "bg-green-500 text-white";
    }
  };

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      "timing_difference": "bg-blue-100 text-blue-800",
      "pending_clearances": "bg-purple-100 text-purple-800",
      "rejected_transactions": "bg-red-100 text-red-800",
      "manual_adjustments": "bg-yellow-100 text-yellow-800",
      "system_adjustments": "bg-green-100 text-green-800",
      "rounding_difference": "bg-gray-100 text-gray-800",
      "unknown_variance": "bg-orange-100 text-orange-800"
    };
    return colors[category] || "bg-gray-100 text-gray-800";
  };

  if (loading) {
    return (
      <div className="p-6 flex justify-center items-center">
        <Loader2 className="w-12 h-12 animate-spin text-brand-blue" />
      </div>
    );
  }

  if (!selectedReport) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6 text-center">
            <AlertCircle className="w-12 h-12 mx-auto text-muted-foreground mb-2" />
            <p className="text-muted-foreground">No GL proofing reports available</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const summary = selectedReport.summary;
  const unreconciled = selectedReport.gl_accounts.filter(a => !a.reconciled);
  const bridges = selectedReport.variance_bridges;
  const criticalBridges = bridges.filter(b => b.priority === "CRITICAL");
  const highBridges = bridges.filter(b => b.priority === "HIGH");

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">GL Justification & Proofing</h1>
          <p className="text-muted-foreground">Day-zero to day-end GL reconciliation with variance bridging</p>
        </div>
        <div className="flex gap-2">
          <Button 
            variant="outline" 
            size="sm" 
            onClick={fetchReports}
            disabled={loading}
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Report Selection */}
      {reports.length > 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Available Reports</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 overflow-x-auto pb-2">
              {reports.map((report) => (
                <Button
                  key={report.report_id}
                  variant={selectedReport?.report_id === report.report_id ? "default" : "outline"}
                  onClick={() => setSelectedReport(report)}
                  className="whitespace-nowrap"
                >
                  {report.run_id} - {report.report_date}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Reconciliation Status Alert */}
      {summary.fully_reconciled ? (
        <Alert className="border-green-200 bg-green-50">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          <AlertTitle className="text-green-900">Fully Reconciled</AlertTitle>
          <AlertDescription className="text-green-800">
            All GL accounts are perfectly reconciled with zero variance.
          </AlertDescription>
        </Alert>
      ) : (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Outstanding Variance</AlertTitle>
          <AlertDescription>
            Total Variance: ₹{summary.total_variance_abs.toLocaleString("en-IN", {maximumFractionDigits: 2})} | 
            Bridged: ₹{summary.total_bridged.toLocaleString("en-IN", {maximumFractionDigits: 2})} | 
            Remaining: ₹{summary.remaining_variance.toLocaleString("en-IN", {maximumFractionDigits: 2})}
          </AlertDescription>
        </Alert>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-foreground">
              {summary.reconciled_accounts}/{summary.total_accounts}
            </div>
            <div className="text-sm text-muted-foreground">Reconciled Accounts</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-red-600">
              ₹{summary.total_variance_abs.toLocaleString("en-IN", {maximumFractionDigits: 0})}
            </div>
            <div className="text-sm text-muted-foreground">Total Variance</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-green-600">
              ₹{summary.total_bridged.toLocaleString("en-IN", {maximumFractionDigits: 0})}
            </div>
            <div className="text-sm text-muted-foreground">Bridged</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-brand-blue">
              {summary.bridging_coverage_percent.toFixed(1)}%
            </div>
            <div className="text-sm text-muted-foreground">Coverage</div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-muted/30">
          <TabsTrigger value="summary" className="data-[state=active]:bg-brand-blue data-[state=active]:text-primary-foreground">
            <TrendingUp className="w-4 h-4 mr-2" />
            Summary
          </TabsTrigger>
          <TabsTrigger value="accounts" className="data-[state=active]:bg-brand-blue data-[state=active]:text-primary-foreground">
            <FileText className="w-4 h-4 mr-2" />
            GL Accounts ({summary.unreconciled_accounts})
          </TabsTrigger>
          <TabsTrigger value="bridges" className="data-[state=active]:bg-brand-blue data-[state=active]:text-primary-foreground">
            <AlertCircle className="w-4 h-4 mr-2" />
            Variance Bridges ({bridges.length})
          </TabsTrigger>
        </TabsList>

        {/* Summary Tab */}
        <TabsContent value="summary" className="space-y-6 mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Reconciliation Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-sm text-muted-foreground">Report Date</div>
                  <div className="text-lg font-semibold">{selectedReport.report_date}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Report ID</div>
                  <div className="text-sm font-mono">{selectedReport.report_id}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Reconciliation Rate</div>
                  <div className="text-lg font-semibold">
                    {((summary.reconciled_accounts / summary.total_accounts) * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">Variance Bridge Coverage</div>
                  <div className="text-lg font-semibold">{summary.bridging_coverage_percent.toFixed(1)}%</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {criticalBridges.length > 0 && (
            <Card className="border-red-200 bg-red-50">
              <CardHeader>
                <CardTitle className="text-red-900">Critical Priority Items</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {criticalBridges.map((bridge) => (
                    <div key={bridge.bridge_id} className="p-3 bg-white border border-red-200 rounded-lg">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="font-semibold text-red-900">{bridge.description}</div>
                          <div className="text-sm text-muted-foreground mt-1">{bridge.justification}</div>
                        </div>
                        <div className="text-right">
                          <div className="font-bold text-red-900">₹{bridge.amount.toLocaleString("en-IN", {maximumFractionDigits: 2})}</div>
                          <Badge className="bg-red-500 text-white mt-1">{bridge.aging_days}d old</Badge>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Accounts Tab */}
        <TabsContent value="accounts" className="space-y-6 mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Unreconciled GL Accounts ({unreconciled.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {unreconciled.length === 0 ? (
                <div className="text-center py-8">
                  <CheckCircle2 className="w-12 h-12 mx-auto text-green-500 mb-2" />
                  <p className="text-muted-foreground">All GL accounts are reconciled</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Account Code</TableHead>
                        <TableHead>Account Name</TableHead>
                        <TableHead className="text-right">Opening Balance</TableHead>
                        <TableHead className="text-right">Closing Balance</TableHead>
                        <TableHead className="text-right">Book Balance</TableHead>
                        <TableHead className="text-right">Variance</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {unreconciled.map((account) => (
                        <TableRow key={account.account_code}>
                          <TableCell className="font-mono font-medium">{account.account_code}</TableCell>
                          <TableCell>{account.account_name}</TableCell>
                          <TableCell className="text-right">
                            ₹{account.opening_balance.toLocaleString("en-IN", {maximumFractionDigits: 2})}
                          </TableCell>
                          <TableCell className="text-right">
                            ₹{account.closing_balance.toLocaleString("en-IN", {maximumFractionDigits: 2})}
                          </TableCell>
                          <TableCell className="text-right">
                            ₹{account.book_balance.toLocaleString("en-IN", {maximumFractionDigits: 2})}
                          </TableCell>
                          <TableCell className="text-right">
                            <Badge variant="destructive">
                              ₹{account.variance_abs.toLocaleString("en-IN", {maximumFractionDigits: 2})}
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

        {/* Variance Bridges Tab */}
        <TabsContent value="bridges" className="space-y-6 mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Variance Bridges ({bridges.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {bridges.length === 0 ? (
                <div className="text-center py-8">
                  <AlertCircle className="w-12 h-12 mx-auto text-muted-foreground mb-2" />
                  <p className="text-muted-foreground">No variance bridges found</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Description</TableHead>
                        <TableHead>Category</TableHead>
                        <TableHead className="text-right">Amount</TableHead>
                        <TableHead>Age</TableHead>
                        <TableHead>Priority</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {bridges.map((bridge) => (
                        <TableRow key={bridge.bridge_id}>
                          <TableCell>
                            <div className="font-semibold">{bridge.description}</div>
                            <div className="text-xs text-muted-foreground">{bridge.justification}</div>
                          </TableCell>
                          <TableCell>
                            <Badge className={getCategoryColor(bridge.category)}>
                              {bridge.category.replace('_', ' ')}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right font-semibold">
                            ₹{bridge.amount.toLocaleString("en-IN", {maximumFractionDigits: 2})}
                          </TableCell>
                          <TableCell>{bridge.aging_days} days</TableCell>
                          <TableCell>
                            <Badge className={getPriorityColor(bridge.priority)}>
                              {bridge.priority}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {bridge.resolved ? (
                              <Badge className="bg-green-500 text-white">Resolved</Badge>
                            ) : (
                              <Badge variant="outline">Pending</Badge>
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
        </TabsContent>
      </Tabs>
    </div>
  );
}
