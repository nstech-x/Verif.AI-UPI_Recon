import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Badge } from "../components/ui/badge";
import { AlertCircle, CheckCircle, Clock, XCircle } from "lucide-react";
import { useToast } from "../hooks/use-toast";

export default function CycleSkip() {
  const { toast } = useToast();
  const [cycleDate, setCycleDate] = useState("");
  const [cycleNumber, setCycleNumber] = useState("");
  const [skipReason, setSkipReason] = useState("");
  const [remarks, setRemarks] = useState("");

  // Demo data - NPCI cycle skip records
  const [cycleSkipRecords] = useState([
    {
      id: "CS2026001",
      cycleDate: "2026-01-15",
      cycleNumber: "C1",
      reason: "System Maintenance",
      status: "Approved",
      createdBy: "Admin",
      createdAt: "2026-01-14 16:30:00",
      approvedBy: "Checker",
      approvedAt: "2026-01-14 17:15:00"
    },
    {
      id: "CS2026002",
      cycleDate: "2026-01-10",
      cycleNumber: "C2",
      reason: "NPCI Scheduled Downtime",
      status: "Approved",
      createdBy: "Ops Team",
      createdAt: "2026-01-09 14:20:00",
      approvedBy: "Manager",
      approvedAt: "2026-01-09 15:45:00"
    },
    {
      id: "CS2026003",
      cycleDate: "2026-01-08",
      cycleNumber: "C3",
      reason: "File Processing Error",
      status: "Pending",
      createdBy: "Admin",
      createdAt: "2026-01-08 10:15:00",
      approvedBy: null,
      approvedAt: null
    },
    {
      id: "CS2026004",
      cycleDate: "2026-01-05",
      cycleNumber: "C1",
      reason: "Network Connectivity Issue",
      status: "Rejected",
      createdBy: "Ops Team",
      createdAt: "2026-01-04 18:30:00",
      approvedBy: "Checker",
      approvedAt: "2026-01-04 19:00:00"
    }
  ]);

  const handleSubmitSkip = () => {
    if (!cycleDate || !cycleNumber || !skipReason) {
      toast({
        title: "Validation Error",
        description: "Please fill all required fields",
        variant: "destructive"
      });
      return;
    }

    toast({
      title: "Cycle Skip Requested (Demo)",
      description: `Cycle skip request for ${cycleDate} - ${cycleNumber} has been submitted for approval`
    });

    // Reset form
    setCycleDate("");
    setCycleNumber("");
    setSkipReason("");
    setRemarks("");
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "Approved":
        return <Badge className="bg-green-500"><CheckCircle className="w-3 h-3 mr-1" /> Approved</Badge>;
      case "Pending":
        return <Badge className="bg-yellow-500"><Clock className="w-3 h-3 mr-1" /> Pending</Badge>;
      case "Rejected":
        return <Badge variant="destructive"><XCircle className="w-3 h-3 mr-1" /> Rejected</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-foreground">NPCI Cycle Skip Management</h1>
        <p className="text-muted-foreground">Manage NPCI cycle skip requests and approvals</p>
      </div>

      {/* Info Banner */}
      <Card className="bg-blue-50 border-blue-200">
        <CardContent className="pt-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5" />
            <div>
              <h3 className="font-semibold text-blue-900">About NPCI Cycle Skip</h3>
              <p className="text-sm text-blue-700 mt-1">
                NPCI Cycle Skip allows authorized users to mark specific settlement cycles as skipped due to 
                system maintenance, network issues, or other valid operational reasons. All skip requests 
                require maker-checker approval before being finalized.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Create Cycle Skip Request */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle>Create Cycle Skip Request</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Cycle Date */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Cycle Date *</Label>
              <Input
                type="date"
                value={cycleDate}
                onChange={(e) => setCycleDate(e.target.value)}
              />
            </div>

            {/* Cycle Number */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Cycle Number *</Label>
              <Select value={cycleNumber} onValueChange={setCycleNumber}>
                <SelectTrigger>
                  <SelectValue placeholder="Select cycle" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="C1">C1 - Morning Settlement</SelectItem>
                  <SelectItem value="C2">C2 - Afternoon Settlement</SelectItem>
                  <SelectItem value="C3">C3 - Evening Settlement</SelectItem>
                  <SelectItem value="C4">C4 - Night Settlement</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Skip Reason */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Skip Reason *</Label>
              <Select value={skipReason} onValueChange={setSkipReason}>
                <SelectTrigger>
                  <SelectValue placeholder="Select reason" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="system_maintenance">System Maintenance</SelectItem>
                  <SelectItem value="npci_downtime">NPCI Scheduled Downtime</SelectItem>
                  <SelectItem value="network_issue">Network Connectivity Issue</SelectItem>
                  <SelectItem value="file_error">File Processing Error</SelectItem>
                  <SelectItem value="reconciliation_issue">Reconciliation Issue</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Remarks */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Remarks</Label>
              <Input
                placeholder="Additional details..."
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 mt-6">
            <Button variant="outline" onClick={() => {
              setCycleDate("");
              setCycleNumber("");
              setSkipReason("");
              setRemarks("");
            }}>
              Clear
            </Button>
            <Button onClick={handleSubmitSkip}>
              Submit for Approval
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Cycle Skip Records */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle>Cycle Skip History</CardTitle>
          <p className="text-sm text-muted-foreground">Recent cycle skip requests and their status</p>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Request ID</TableHead>
                <TableHead>Cycle Date</TableHead>
                <TableHead>Cycle</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created By</TableHead>
                <TableHead>Created At</TableHead>
                <TableHead>Approved By</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cycleSkipRecords.map((record) => (
                <TableRow key={record.id}>
                  <TableCell className="font-medium">{record.id}</TableCell>
                  <TableCell>{record.cycleDate}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{record.cycleNumber}</Badge>
                  </TableCell>
                  <TableCell>{record.reason}</TableCell>
                  <TableCell>{getStatusBadge(record.status)}</TableCell>
                  <TableCell>{record.createdBy}</TableCell>
                  <TableCell className="text-xs">{record.createdAt}</TableCell>
                  <TableCell>{record.approvedBy || '-'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Statistics */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Requests</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{cycleSkipRecords.length}</div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Pending Approval</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">
              {cycleSkipRecords.filter(r => r.status === "Pending").length}
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Approved This Month</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {cycleSkipRecords.filter(r => r.status === "Approved").length}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}