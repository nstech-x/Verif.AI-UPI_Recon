import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Eye, Plus, AlertTriangle, Search } from "lucide-react";
import { useToast } from "../hooks/use-toast";

// Mock watchlist data
const WATCHLIST_ENTRIES = [
  {
    id: "WL001",
    rrn: "636397811101708",
    amount: 25000.00,
    status: "under_review",
    reason: "High value transaction with pattern anomaly",
    addedDate: "2026-01-13",
    addedBy: "System AI",
    priority: "high"
  },
  {
    id: "WL002",
    rrn: "636397811101712",
    amount: 150000.00,
    status: "flagged",
    reason: "Exceeds threshold for manual verification",
    addedDate: "2026-01-14",
    addedBy: "admin",
    priority: "critical"
  },
  {
    id: "WL003",
    rrn: "636397811101715",
    amount: 35000.00,
    status: "under_review",
    reason: "Multiple failed attempts detected",
    addedDate: "2026-01-14",
    addedBy: "maker1",
    priority: "medium"
  }
];

export default function Watchlist() {
  const { toast } = useToast();
  const [searchTerm, setSearchTerm] = useState("");
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [newEntry, setNewEntry] = useState({
    rrn: "",
    reason: "",
    priority: "medium"
  });

  const handleAddToWatchlist = () => {
    // Demo mode - just show success toast
    toast({
      title: "Added to Watchlist (Demo Mode)",
      description: `RRN ${newEntry.rrn} has been flagged for review.`,
    });
    
    setNewEntry({ rrn: "", reason: "", priority: "medium" });
    setShowAddDialog(false);
  };

  const handleMarkReviewed = (id: string) => {
    toast({
      title: "Marked as Reviewed (Demo Mode)",
      description: `Watchlist entry ${id} updated.`,
    });
  };

  const getPriorityBadge = (priority: string) => {
    const variants: Record<string, string> = {
      critical: "bg-red-100 text-red-800 border-red-300",
      high: "bg-orange-100 text-orange-800 border-orange-300",
      medium: "bg-yellow-100 text-yellow-800 border-yellow-300",
      low: "bg-blue-100 text-blue-800 border-blue-300"
    };
    
    return variants[priority] || variants.medium;
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, string> = {
      flagged: "bg-red-100 text-red-800 border-red-300",
      under_review: "bg-yellow-100 text-yellow-800 border-yellow-300",
      reviewed: "bg-green-100 text-green-800 border-green-300"
    };
    
    return variants[status] || variants.under_review;
  };

  const filteredEntries = WATCHLIST_ENTRIES.filter(entry =>
    entry.rrn.toLowerCase().includes(searchTerm.toLowerCase()) ||
    entry.reason.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground flex items-center gap-2">
            <Eye className="w-6 h-6 text-brand-blue" />
            Watchlist
          </h1>
          <p className="text-sm text-muted-foreground">Monitor flagged transactions for review</p>
        </div>
        
        <Button 
          onClick={() => setShowAddDialog(true)}
          className="bg-brand-blue hover:bg-brand-mid text-white"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add to Watchlist
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Flagged</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{WATCHLIST_ENTRIES.length}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Under Review</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">
              {WATCHLIST_ENTRIES.filter(e => e.status === "under_review").length}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Critical Priority</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {WATCHLIST_ENTRIES.filter(e => e.priority === "critical").length}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">High Value</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {WATCHLIST_ENTRIES.filter(e => e.amount > 50000).length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search by RRN or reason..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Watchlist Table */}
      <Card>
        <CardHeader>
          <CardTitle>Flagged Transactions</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>RRN</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Added By</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredEntries.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell className="font-mono text-sm">{entry.rrn}</TableCell>
                  <TableCell className="font-semibold">₹{entry.amount.toLocaleString()}</TableCell>
                  <TableCell className="max-w-xs text-sm">{entry.reason}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className={getStatusBadge(entry.status)}>
                      {entry.status.replace('_', ' ')}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className={getPriorityBadge(entry.priority)}>
                      {entry.priority}
                    </Badge>
                  </TableCell>
                  <TableCell>{entry.addedBy}</TableCell>
                  <TableCell>{entry.addedDate}</TableCell>
                  <TableCell>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleMarkReviewed(entry.id)}
                    >
                      Review
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Add to Watchlist Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Transaction to Watchlist</DialogTitle>
            <DialogDescription>
              Flag a transaction for manual review and monitoring
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="rrn">RRN / Transaction ID</Label>
              <Input
                id="rrn"
                placeholder="Enter RRN or Transaction ID"
                value={newEntry.rrn}
                onChange={(e) => setNewEntry({ ...newEntry, rrn: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="reason">Reason for Flagging</Label>
              <Textarea
                id="reason"
                placeholder="Describe why this transaction needs review..."
                value={newEntry.reason}
                onChange={(e) => setNewEntry({ ...newEntry, reason: e.target.value })}
                rows={3}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="priority">Priority Level</Label>
              <select
                id="priority"
                value={newEntry.priority}
                onChange={(e) => setNewEntry({ ...newEntry, priority: e.target.value })}
                className="w-full border rounded-md px-3 py-2"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleAddToWatchlist}
              disabled={!newEntry.rrn || !newEntry.reason}
              className="bg-brand-blue hover:bg-brand-mid text-white"
            >
              <AlertTriangle className="w-4 h-4 mr-2" />
              Add to Watchlist
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}