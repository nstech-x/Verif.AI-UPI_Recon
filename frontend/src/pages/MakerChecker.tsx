import { useState } from "react";
import React from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { CheckCircle, XCircle, Clock, UserCheck, History } from "lucide-react";
import { useToast } from "../hooks/use-toast";
import DemoBadge from "../components/DemoBadge";

// Mock maker-checker data
const PENDING_APPROVALS = [
  {
    id: "APP001",
    action: "force_match",
    rrn: "636397811101710",
    amount: 12300.00,
    status: "pending_checker_approval",
    createdBy: "maker1",
    createdAt: "2026-01-14T09:30:00Z",
    reason: "Manual match required - CBS and NPCI records found",
  },
  {
    id: "APP002",
    action: "reconcile_batch",
    runId: "RUN_20260114_095430",
    status: "pending_checker_approval",
    createdBy: "Verif.AI",
    createdAt: "2026-01-14T09:54:30Z",
    details: {
      totalTransactions: 3256,
      matched: 2987,
      unmatched: 189
    },
  }
];

const APPROVAL_HISTORY = [
  {
    id: "APP_HIST_001",
    action: "force_match",
    rrn: "636397811101708",
    status: "approved",
    createdBy: "maker1",
    approvedBy: "checker1",
    approvedAt: "2026-01-13T14:22:00Z",
    comments: "Verified with CBS team - approved"
  },
  {
    id: "APP_HIST_002",
    action: "rollback",
    runId: "RUN_20260113_143022",
    status: "rejected",
    createdBy: "maker1",
    approvedBy: "checker1",
    approvedAt: "2026-01-13T15:10:00Z",
    comments: "Incomplete data - rejected"
  }
];

interface MakerCheckerProps {
  dateFrom?: string;
  dateTo?: string;
}

export default function MakerChecker({ dateFrom, dateTo }: MakerCheckerProps) {
  const { toast } = useToast();
  
  // Log on mount to verify component loads with date props
  React.useEffect(() => {
    console.log('[MakerChecker] Mounted with dates:', { dateFrom, dateTo });
  }, [dateFrom, dateTo]);

  const handleApprove = (id: string) => {
    toast({
      title: "Approved (Demo Mode)",
      description: `Request ${id} has been approved successfully.`,
    });
  };

  const handleReject = (id: string) => {
    toast({
      title: "Rejected (Demo Mode)",
      description: `Request ${id} has been rejected.`,
      variant: "destructive",
    });
  };

  const formatDateTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleString('en-IN', {
      dateStyle: 'medium',
      timeStyle: 'short'
    });
  };

  const formatAction = (action: string) => {
    return action.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };


  const baseDate = dateFrom || dateTo || null;
  const withBaseDate = (timestamp: string) => {
    if (!baseDate) return timestamp;
    try {
      const t = new Date(timestamp);
      const base = new Date(baseDate);
      base.setHours(t.getHours(), t.getMinutes(), t.getSeconds(), t.getMilliseconds());
      return base.toISOString();
    } catch (e) {
      return timestamp;
    }
  };

  const pendingApprovals = baseDate
    ? PENDING_APPROVALS.map(a => ({ ...a, createdAt: withBaseDate(a.createdAt) }))
    : PENDING_APPROVALS;

  const historyApprovals = baseDate
    ? APPROVAL_HISTORY.map(h => ({ ...h, approvedAt: withBaseDate(h.approvedAt) }))
    : APPROVAL_HISTORY;

  const filteredPending = pendingApprovals.filter(a => {
    if (!dateFrom && !dateTo) return true;
    try {
      const created = new Date(a.createdAt);
      if (dateFrom) {
        const from = new Date(dateFrom);
        if (created < from) return false;
      }
      if (dateTo) {
        const to = new Date(dateTo);
        to.setHours(23,59,59,999);
        if (created > to) return false;
      }
      return true;
    } catch (e) {
      return true;
    }
  });

  const filteredHistory = historyApprovals.filter(item => {
    if (!dateFrom && !dateTo) return true;
    try {
      const approved = new Date(item.approvedAt);
      if (dateFrom) {
        const from = new Date(dateFrom);
        if (approved < from) return false;
      }
      if (dateTo) {
        const to = new Date(dateTo);
        to.setHours(23,59,59,999);
        if (approved > to) return false;
      }
      return true;
    } catch (e) {
      return true;
    }
  });


  return (
    <div className="p-6 space-y-6">
      {/* Debug Info */}
      <div className="text-xs text-muted-foreground bg-muted/30 p-2 rounded">
        Maker-Checker | Pending: {pendingApprovals.length} | History: {historyApprovals.length} | Dates: {dateFrom} to {dateTo}
      </div>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-foreground flex items-center gap-2">
              <UserCheck className="w-6 h-6 text-brand-blue" />
              Maker-Checker Workflow
            </h1>
            <DemoBadge />
          </div>
          <p className="text-sm text-muted-foreground">Approval workflow for critical operations</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Pending Approvals</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">{filteredPending.length}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Approved Today</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {filteredHistory.filter(h => h.status === "approved").length}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Rejected Today</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {filteredHistory.filter(h => h.status === "rejected").length}
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="pending" className="w-full">
        <TabsList className="bg-muted/30">
          <TabsTrigger value="pending">
            <Clock className="w-4 h-4 mr-2" />
            Pending Approvals
          </TabsTrigger>
          <TabsTrigger value="history">
            <History className="w-4 h-4 mr-2" />
            Approval History
          </TabsTrigger>
        </TabsList>

        {/* Pending Approvals */}
          <TabsContent value="pending" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Pending Approval Requests</CardTitle>
              <CardDescription>Actions requiring checker approval</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Action</TableHead>
                    <TableHead>Details</TableHead>
                    <TableHead>Created By</TableHead>
                    <TableHead>Created At</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredPending.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                        No pending approvals found for the selected date range
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredPending.map((approval) => (
                      <TableRow key={approval.id}>
                        <TableCell className="font-medium">
                          {formatAction(approval.action)}
                        </TableCell>
                        <TableCell>
                          <div className="space-y-1 text-sm">
                            {approval.rrn && <div>RRN: {approval.rrn}</div>}
                            {approval.amount && <div>Amount: ₹{approval.amount.toLocaleString()}</div>}
                            {approval.runId && <div className="font-mono text-xs">{approval.runId}</div>}
                            {approval.reason && <div className="text-muted-foreground">{approval.reason}</div>}
                            {approval.details && (
                              <div className="text-xs text-muted-foreground">
                                Total: {approval.details.totalTransactions}, 
                                Matched: {approval.details.matched}, 
                                Unmatched: {approval.details.unmatched}
                              </div>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>{approval.createdBy}</TableCell>
                        <TableCell>{formatDateTime(approval.createdAt)}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="bg-orange-50 text-orange-700 border-orange-300">
                            Pending Approval
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              onClick={() => handleApprove(approval.id)}
                              className="bg-green-600 hover:bg-green-700 text-white"
                            >
                              <CheckCircle className="w-4 h-4 mr-1" />
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => handleReject(approval.id)}
                            >
                              <XCircle className="w-4 h-4 mr-1" />
                              Reject
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
</TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Approval History */}
        <TabsContent value="history" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Approval History</CardTitle>
              <CardDescription>Past approval decisions</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Action</TableHead>
                    <TableHead>Details</TableHead>
                    <TableHead>Maker</TableHead>
                    <TableHead>Checker</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Comments</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredHistory.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                        No approval history found for the selected date range
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredHistory.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="font-medium">
                          {formatAction(item.action)}
                        </TableCell>
                        <TableCell>
                          <div className="text-sm">
                            {item.rrn && <div>RRN: {item.rrn}</div>}
                            {item.runId && <div className="font-mono text-xs">{item.runId}</div>}
                          </div>
                        </TableCell>
                        <TableCell>{item.createdBy}</TableCell>
                        <TableCell>{item.approvedBy}</TableCell>
                        <TableCell>{formatDateTime(item.approvedAt)}</TableCell>
                        <TableCell>
                          <Badge 
                            variant="outline" 
                            className={
                              item.status === "approved" 
                                ? "bg-green-50 text-green-700 border-green-300"
                                : "bg-red-50 text-red-700 border-red-300"
                            }
                          >
                            {item.status === "approved" ? "Approved" : "Rejected"}
                          </Badge>
                        </TableCell>
                        <TableCell className="max-w-xs text-sm text-muted-foreground">
                          {item.comments}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
</TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
