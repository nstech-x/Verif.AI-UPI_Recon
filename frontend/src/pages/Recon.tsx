import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/label";
import { Loader2, CheckCircle2, Clock } from "lucide-react";
import { useToast } from "../hooks/use-toast";
import CycleSelector from "../components/CycleSelector";
import DirectionSelector from "../components/DirectionSelector";
import { apiClient } from "../lib/api";
import { generateDemoSummary } from "../lib/demoData";

export default function Recon() {
  const { toast } = useToast();
  const [report, setReport] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [reconciliating, setReconciliating] = useState(false);
  const [summary, setSummary] = useState<any>(null);
  const [selectedCycle, setSelectedCycle] = useState("all");
  const [selectedDirection, setSelectedDirection] = useState("inward");
  const [selectedRunId, setSelectedRunId] = useState<string>("");

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        setLoading(true);
        const response = await apiClient.getSummary();
        console.log('API Response:', response);
        setSummary(response);

        // Generate report text from real data
        const reportText = `Reconciliation Report
Run ID: ${response.run_id || 'N/A'}
Status: ${response.status || 'completed'}
Generated: ${response.generated_at || new Date().toISOString()}

=== Summary ===
Total Transactions: ${(response.totals?.count || response.total_transactions || 0).toLocaleString()}
Matched: ${(response.matched?.count || 0).toLocaleString()} (${Math.round(((response.matched?.count || 0) / (response.totals?.count || response.total_transactions || 1)) * 100)}%)
Partial Matches: ${(response.partial_matches?.count || 0).toLocaleString()} (${Math.round(((response.partial_matches?.count || 0) / (response.totals?.count || response.total_transactions || 1)) * 100)}%)
Hanging: ${(response.hanging?.count || 0).toLocaleString()} (${Math.round(((response.hanging?.count || 0) / (response.totals?.count || response.total_transactions || 1)) * 100)}%)
Unmatched: ${(response.unmatched?.count || 0).toLocaleString()} (${Math.round(((response.unmatched?.count || 0) / (response.totals?.count || response.total_transactions || 1)) * 100)}%)

Real-time reconciliation data from backend.`;
        setReport(reportText);
      } catch (error) {
        console.error('Failed to fetch summary:', error);
        toast({
          title: "Error",
          description: "Failed to load reconciliation summary. Please try again.",
          variant: "destructive"
        });
        setSummary(null);
        setReport("Failed to load reconciliation report.");
      } finally {
        setLoading(false);
      }
    };

    fetchSummary();
  }, []);

  const handleRunRecon = async () => {
    try {
      setReconciliating(true);
      
      // Call the actual reconciliation API
      const response = await apiClient.runReconciliation(
        selectedRunId || undefined, // Use selected RUN ID or let backend use latest
        selectedDirection.toUpperCase()
      );

      toast({
        title: "Reconciliation completed",
        description: `Successfully processed ${response.matched_count + response.unmatched_count + response.exception_count + response.partial_match_count + response.hanging_count} transactions. Matched: ${response.matched_count}, Unmatched: ${response.unmatched_count}, Hanging: ${response.hanging_count}`,
      });

      // Refresh the summary after reconciliation
      const updatedSummary = await apiClient.getSummary();
      setSummary(updatedSummary);

      // Dispatch event to refresh dashboard
      window.dispatchEvent(new CustomEvent('reconciliationComplete'));

      // Update report text with new data
      const reportText = `Reconciliation Report
Run ID: ${updatedSummary.run_id || 'N/A'}
Status: ${updatedSummary.status || 'completed'}
Generated: ${updatedSummary.generated_at || new Date().toISOString()}

=== Summary ===
Total Transactions: ${(updatedSummary.totals?.count || updatedSummary.total_transactions || 0).toLocaleString()}
Matched: ${(updatedSummary.matched?.count || 0).toLocaleString()} (${Math.round(((updatedSummary.matched?.count || 0) / (updatedSummary.totals?.count || updatedSummary.total_transactions || 1)) * 100)}%)
Partial Matches: ${(updatedSummary.partial_matches?.count || 0).toLocaleString()} (${Math.round(((updatedSummary.partial_matches?.count || 0) / (updatedSummary.totals?.count || updatedSummary.total_transactions || 1)) * 100)}%)
Hanging: ${(updatedSummary.hanging?.count || 0).toLocaleString()} (${Math.round(((updatedSummary.hanging?.count || 0) / (updatedSummary.totals?.count || updatedSummary.total_transactions || 1)) * 100)}%)
Unmatched: ${(updatedSummary.unmatched?.count || 0).toLocaleString()} (${Math.round(((updatedSummary.unmatched?.count || 0) / (updatedSummary.totals?.count || updatedSummary.total_transactions || 1)) * 100)}%)

Real-time reconciliation data from backend.`;
      setReport(reportText);

    } catch (error: any) {
      console.error('Reconciliation failed:', error);
      toast({
        title: "Reconciliation failed",
        description: error.response?.data?.detail || error.message || "An error occurred during reconciliation",
        variant: "destructive",
      });
    } finally {
      setReconciliating(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Recon Workflow</h1>
        <p className="text-muted-foreground">
          Run reconciliation and view reports
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6">
        {/* Status Banner */}
        {summary && summary.run_id && (
          <Card className="shadow-sm bg-gradient-to-r from-blue-50 to-card border-blue-200">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-lg">
                    Current Reconciliation Status
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Run ID: {summary.run_id}
                  </p>
                  <div className="flex items-center gap-1 text-sm text-muted-foreground mt-1">
                    <span>Status:</span>
                    {reconciliating ? (
                      <span className="flex items-center gap-1 text-blue-600">
                        <Clock className="h-4 w-4 animate-spin" /> Running...
                      </span>
                    ) : summary.status === "completed" ? (
                      <span className="flex items-center gap-1 text-green-600">
                        <CheckCircle2 className="h-4 w-4" /> Completed
                      </span>
                    ) : (
                      <span>{summary.status}</span>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-3xl font-bold text-green-600">
                    {(summary.matched?.count ?? summary.matched ?? 0).toLocaleString()}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Transactions Matched
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Run Reconciliation Section */}
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-xl">Run Reconciliation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <Label className="text-sm font-medium">RUN ID (Optional)</Label>
                <input
                  type="text"
                  value={selectedRunId}
                  onChange={(e) => setSelectedRunId(e.target.value)}
                  placeholder="Leave empty to use latest run"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-sm font-medium">Cycle</Label>
                <CycleSelector value={selectedCycle} onValueChange={setSelectedCycle} />
              </div>

            </div>

            <div className="flex items-center justify-between pt-4 border-t">
              <p className="text-xs text-muted-foreground max-w-[60%]">
                Configure the cycle and direction parameters above to initiate a new reconciliation process.
              </p>
              <Button
                size="sm"
                className="bg-brand-blue hover:bg-brand-mid px-6"
                onClick={handleRunRecon}
                disabled={reconciliating}
              >
                {reconciliating ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Processing...
                  </>
                ) : (
                  "Run Recon"
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}