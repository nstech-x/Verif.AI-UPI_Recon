import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Input } from "../components/ui/input";
import { AlertCircle, Clock, CheckCircle, FileText, Plus, Search, Filter, Eye, Edit, Trash2, Calendar, DollarSign } from "lucide-react";
import { generateDemoDisputes, getDisputeStats } from "../lib/disputeDemoData";
import { Dispute, TxnSubtype, DisputeStatusGroup, getStageName } from "../types/dispute";
import { getDisputeCategories, getReasonCodes } from "../constants/disputeMaster";
import { useToast } from "../hooks/use-toast";

export default function Disputes() {
  const { toast } = useToast();
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [filteredDisputes, setFilteredDisputes] = useState<Dispute[]>([]);
  const [activeTab, setActiveTab] = useState<"open" | "working" | "closed">("open");
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [selectedDispute, setSelectedDispute] = useState<Dispute | null>(null);
  const [isDetailDialogOpen, setIsDetailDialogOpen] = useState(false);
  
  // Search and Filter State
  const [searchTerm, setSearchTerm] = useState("");
  const [filterTxnSubtype, setFilterTxnSubtype] = useState<string>("all");
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [filterTATStatus, setFilterTATStatus] = useState<string>("all");
  
  // Create Dispute Form State
  const [txnSubtype, setTxnSubtype] = useState<TxnSubtype>("U2");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedReasonCode, setSelectedReasonCode] = useState("");
  const [transactionRRN, setTransactionRRN] = useState("");
  const [transactionAmount, setTransactionAmount] = useState("");

  useEffect(() => {
    // Load demo disputes
    const demoDisputes = generateDemoDisputes();
    setDisputes(demoDisputes);
    filterDisputes(demoDisputes, activeTab, searchTerm, filterTxnSubtype, filterCategory, filterTATStatus);
  }, []);

  useEffect(() => {
    filterDisputes(disputes, activeTab, searchTerm, filterTxnSubtype, filterCategory, filterTATStatus);
  }, [activeTab, disputes, searchTerm, filterTxnSubtype, filterCategory, filterTATStatus]);

  const filterDisputes = (allDisputes: Dispute[], status: string, search: string, txnSubtype: string, category: string, tatStatus: string) => {
    let filtered = allDisputes.filter(d => {
      // Status filter
      switch (status) {
        case "open":
          if (d.statusGroup !== "Open") return false;
          break;
        case "working":
          if (d.statusGroup !== "Working") return false;
          break;
        case "closed":
          if (d.statusGroup !== "Closed") return false;
          break;
      }

      // Search filter
      if (search) {
        const searchLower = search.toLowerCase();
        if (!d.disputeId.toLowerCase().includes(searchLower) &&
            !d.transactionRRN.toLowerCase().includes(searchLower) &&
            !d.reasonDescription.toLowerCase().includes(searchLower)) {
          return false;
        }
      }

      // Transaction subtype filter
      if (txnSubtype !== "all" && d.txnSubtype !== txnSubtype) {
        return false;
      }

      // Category filter
      if (category !== "all" && d.disputeCategory !== category) {
        return false;
      }

      // TAT status filter
      if (tatStatus !== "all") {
        const tatBadge = getTATStatusBadge(d);
        const tatText = tatBadge.props.children;
        if (tatStatus === "breached" && tatText !== "TAT Breached") return false;
        if (tatStatus === "approaching" && tatText !== "Approaching TAT") return false;
        if (tatStatus === "within" && tatText !== "Within TAT") return false;
      }

      return true;
    });
    setFilteredDisputes(filtered);
  };

  const stats = getDisputeStats(disputes);

  // Get available categories based on selected subtype
  const availableCategories = getDisputeCategories(txnSubtype);

  // Get available reason codes based on selected subtype and category
  const availableReasonCodes = selectedCategory 
    ? getReasonCodes(txnSubtype, selectedCategory)
    : [];

  // Get selected reason code details
  const selectedReasonDetails = availableReasonCodes.find(
    r => r.reasonCode === selectedReasonCode
  );

  const handleCreateDispute = () => {
    if (!selectedReasonCode || !transactionRRN) {
      toast({
        title: "Validation Error",
        description: "Please fill all required fields",
        variant: "destructive"
      });
      return;
    }

    // Create new dispute
    const newDispute: Dispute = {
      disputeId: `DIS${new Date().getFullYear()}${String(new Date().getMonth() + 1).padStart(2, '0')}${String(Math.floor(Math.random() * 10000)).padStart(4, '0')}`,
      txnSubtype: txnSubtype,
      disputeCategory: selectedCategory,
      stageCode: "B", // Always starts at Raise
      reasonCode: selectedReasonCode,
      reasonDescription: selectedReasonDetails?.reasonDescription || "",
      tatDays: selectedReasonDetails?.tatDays || 90,
      tatReference: selectedReasonDetails?.tatReference || "Txn Date",
      statusGroup: "Open",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      transactionRRN: transactionRRN,
      transactionAmount: transactionAmount ? parseFloat(transactionAmount) : undefined,
      transactionDate: new Date().toISOString()
    };

    setDisputes([newDispute, ...disputes]);
    setIsCreateDialogOpen(false);
    
    // Reset form
    setTxnSubtype("U2");
    setSelectedCategory("");
    setSelectedReasonCode("");
    setTransactionRRN("");
    setTransactionAmount("");

    toast({
      title: "Dispute Created (Demo)",
      description: `Dispute ${newDispute.disputeId} has been created successfully`
    });
  };

  const handleViewDispute = (dispute: Dispute) => {
    setSelectedDispute(dispute);
    setIsDetailDialogOpen(true);
  };

  const handleUpdateDisputeStatus = (disputeId: string, newStatus: DisputeStatusGroup) => {
    // In a real app, this would call an API
    setDisputes(disputes.map(d => 
      d.disputeId === disputeId 
        ? { ...d, statusGroup: newStatus, updatedAt: new Date().toISOString() }
        : d
    ));
    toast({
      title: "Status Updated",
      description: `Dispute ${disputeId} status updated to ${newStatus}`
    });
  };

  const handleDeleteDispute = (disputeId: string) => {
    // In a real app, this would call an API
    setDisputes(disputes.filter(d => d.disputeId !== disputeId));
    toast({
      title: "Dispute Deleted",
      description: `Dispute ${disputeId} has been deleted`
    });
  };

  const getTATStatusBadge = (dispute: Dispute) => {
    const createdDate = new Date(dispute.createdAt);
    const today = new Date();
    const daysPassed = Math.floor((today.getTime() - createdDate.getTime()) / (1000 * 60 * 60 * 24));
    const tatDays = dispute.tatDays;
    
    if (daysPassed >= tatDays) {
      return <Badge variant="destructive">TAT Breached</Badge>;
    } else if (daysPassed >= tatDays * 0.8) {
      return <Badge className="bg-yellow-500">Approaching TAT</Badge>;
    } else {
      return <Badge className="bg-green-500">Within TAT</Badge>;
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Dispute Management</h1>
          <p className="text-muted-foreground">NPCI/RBI Compliant Dispute Resolution</p>
        </div>
        
        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2">
              <Plus className="w-4 h-4" />
              Create Dispute
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Create New Dispute</DialogTitle>
              <DialogDescription>
                Enter dispute details based on NPCI dispute master
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 py-4">
              {/* Transaction Subtype */}
              <div className="space-y-2">
                <Label className="text-sm font-medium">Transaction Subtype *</Label>
                <Select value={txnSubtype} onValueChange={(val) => {
                  setTxnSubtype(val as TxnSubtype);
                  setSelectedCategory("");
                  setSelectedReasonCode("");
                }}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="U2">U2 - Chargeback</SelectItem>
                    <SelectItem value="U3">U3 - Fraud</SelectItem>
                    <SelectItem value="UC">UC - Credit Adjustment</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Dispute Category (Dispute Action) */}
              <div className="space-y-2">
                <Label className="text-sm font-medium">Dispute Action *</Label>
                <Select value={selectedCategory} onValueChange={(val) => {
                  setSelectedCategory(val);
                  setSelectedReasonCode("");
                }}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select dispute action" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableCategories.length === 0 ? (
                      <SelectItem value="none" disabled>No actions available</SelectItem>
                    ) : (
                      availableCategories.map(cat => (
                        <SelectItem key={cat} value={cat}>{cat}</SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Select the NPCI dispute action for this transaction
                </p>
              </div>

              {/* Reason Code */}
              <div className="space-y-2">
                <Label className="text-sm font-medium">Reason Code *</Label>
                <Select 
                  value={selectedReasonCode} 
                  onValueChange={setSelectedReasonCode}
                  disabled={!selectedCategory}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={!selectedCategory ? "Select category first" : "Select reason code"} />
                  </SelectTrigger>
                  <SelectContent>
                    {availableReasonCodes.length === 0 && selectedCategory ? (
                      <SelectItem value="none" disabled>No reason codes available</SelectItem>
                    ) : (
                      availableReasonCodes.map(reason => (
                        <SelectItem key={reason.reasonCode} value={reason.reasonCode}>
                          {reason.reasonCode} – {reason.reasonDescription}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
                {selectedCategory && availableReasonCodes.length === 0 && (
                  <p className="text-xs text-muted-foreground">
                    No reason codes found for {txnSubtype} - {selectedCategory}
                  </p>
                )}
              </div>

              {/* Auto-populated fields */}
              {selectedReasonDetails && (
                <div className="space-y-3 p-4 bg-muted/50 rounded-lg">
                  <div>
                    <Label className="text-xs text-muted-foreground">Reason Description</Label>
                    <p className="text-sm font-medium">{selectedReasonDetails.reasonDescription}</p>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label className="text-xs text-muted-foreground">TAT (Days)</Label>
                      <p className="text-sm font-medium">{selectedReasonDetails.tatDays} days</p>
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground">TAT Reference</Label>
                      <p className="text-sm font-medium">{selectedReasonDetails.tatReference}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Transaction Details */}
              <div className="space-y-2">
                <Label className="text-sm font-medium">Transaction RRN *</Label>
                <Input 
                  placeholder="Enter RRN"
                  value={transactionRRN}
                  onChange={(e) => setTransactionRRN(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label className="text-sm font-medium">Transaction Amount (₹)</Label>
                <Input 
                  type="number"
                  placeholder="0.00"
                  value={transactionAmount}
                  onChange={(e) => setTransactionAmount(e.target.value)}
                />
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreateDispute}>
                Create Dispute
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Search and Filters */}
      <Card className="shadow-sm">
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                <Input
                  placeholder="Search by Dispute ID, RRN, or Description..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <Select value={filterTxnSubtype} onValueChange={setFilterTxnSubtype}>
                <SelectTrigger className="w-32">
                  <SelectValue placeholder="Txn Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="U2">U2</SelectItem>
                  <SelectItem value="U3">U3</SelectItem>
                  <SelectItem value="UC">UC</SelectItem>
                </SelectContent>
              </Select>
              
              <Select value={filterCategory} onValueChange={setFilterCategory}>
                <SelectTrigger className="w-40">
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  <SelectItem value="Chargeback">Chargeback</SelectItem>
                  <SelectItem value="Fraud">Fraud</SelectItem>
                  <SelectItem value="Credit Adjustment">Credit Adjustment</SelectItem>
                </SelectContent>
              </Select>
              
              <Select value={filterTATStatus} onValueChange={setFilterTATStatus}>
                <SelectTrigger className="w-32">
                  <SelectValue placeholder="TAT Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All TAT</SelectItem>
                  <SelectItem value="within">Within TAT</SelectItem>
                  <SelectItem value="approaching">Approaching</SelectItem>
                  <SelectItem value="breached">Breached</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="shadow-sm border-l-4 border-l-blue-500">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Total Disputes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-3xl font-bold text-blue-600">{stats.total}</div>
                <div className="text-xs text-muted-foreground mt-1">All stages combined</div>
              </div>
              <FileText className="h-10 w-10 text-blue-600 opacity-20" />
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm border-l-4 border-l-orange-500">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              Open
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-3xl font-bold text-orange-600">{stats.byStatus.open}</div>
                <div className="text-xs text-muted-foreground mt-1">Raise/Accept/Represent</div>
              </div>
              <AlertCircle className="h-10 w-10 text-orange-600 opacity-20" />
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm border-l-4 border-l-blue-500">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Working
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-3xl font-bold text-blue-600">{stats.byStatus.working}</div>
                <div className="text-xs text-muted-foreground mt-1">Pre-Arb/Arb/Deferred</div>
              </div>
              <Clock className="h-10 w-10 text-blue-600 opacity-20" />
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm border-l-4 border-l-green-500">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <CheckCircle className="h-4 w-4" />
              Closed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-3xl font-bold text-green-600">{stats.byStatus.closed}</div>
                <div className="text-xs text-muted-foreground mt-1">Resolved disputes</div>
              </div>
              <CheckCircle className="h-10 w-10 text-green-600 opacity-20" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* TAT Status Overview */}
      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            TAT Compliance Overview
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="text-center p-6 bg-green-50 rounded-lg border border-green-200 hover:bg-green-100 transition-colors">
              <div className="text-3xl font-bold text-green-600 mb-2">{stats.tatStatus.withinTAT}</div>
              <div className="text-sm font-medium text-green-800 mb-1">Within TAT</div>
              <div className="text-xs text-green-600">On track for resolution</div>
            </div>
            <div className="text-center p-6 bg-yellow-50 rounded-lg border border-yellow-200 hover:bg-yellow-100 transition-colors">
              <div className="text-3xl font-bold text-yellow-600 mb-2">{stats.tatStatus.approachingTAT}</div>
              <div className="text-sm font-medium text-yellow-800 mb-1">Approaching TAT</div>
              <div className="text-xs text-yellow-600">Requires attention</div>
            </div>
            <div className="text-center p-6 bg-red-50 rounded-lg border border-red-200 hover:bg-red-100 transition-colors">
              <div className="text-3xl font-bold text-red-600 mb-2">{stats.tatStatus.tatBreached}</div>
              <div className="text-sm font-medium text-red-800 mb-1">TAT Breached</div>
              <div className="text-xs text-red-600">Urgent action required</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Dispute Tables by Status */}
      <Tabs value={activeTab} onValueChange={(val) => setActiveTab(val as any)}>
        <TabsList>
          <TabsTrigger value="open" className="gap-2">
            <AlertCircle className="w-4 h-4" />
            Open ({stats.byStatus.open})
          </TabsTrigger>
          <TabsTrigger value="working" className="gap-2">
            <Clock className="w-4 h-4" />
            Working ({stats.byStatus.working})
          </TabsTrigger>
          <TabsTrigger value="closed" className="gap-2">
            <CheckCircle className="w-4 h-4" />
            Closed ({stats.byStatus.closed})
          </TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab} className="mt-6">
          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle>
                {activeTab === "open" && "Open Disputes"}
                {activeTab === "working" && "Working Disputes"}
                {activeTab === "closed" && "Closed Disputes"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Dispute ID</TableHead>
                    <TableHead>Txn Subtype</TableHead>
                    <TableHead>Dispute Action</TableHead>
                    <TableHead>Reason Code</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Stage</TableHead>
                    <TableHead>TAT</TableHead>
                    <TableHead>TAT Status</TableHead>
                    <TableHead>RRN</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredDisputes.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={10} className="text-center text-muted-foreground py-8">
                        No {activeTab} disputes found matching your criteria
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredDisputes.map((dispute) => (
                      <TableRow key={dispute.disputeId} className="hover:bg-muted/50">
                        <TableCell className="font-medium font-mono">{dispute.disputeId}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="font-semibold">{dispute.txnSubtype}</Badge>
                        </TableCell>
                        <TableCell className="font-medium">{dispute.disputeCategory}</TableCell>
                        <TableCell className="font-mono text-xs bg-muted px-2 py-1 rounded">{dispute.reasonCode}</TableCell>
                        <TableCell className="max-w-xs">
                          <div className="truncate" title={dispute.reasonDescription}>
                            {dispute.reasonDescription}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary" className="text-xs">
                            {getStageName(dispute.stageCode)}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs">
                          <div className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {dispute.tatDays}d
                          </div>
                          <div className="text-muted-foreground text-xs">
                            from {dispute.tatReference}
                          </div>
                        </TableCell>
                        <TableCell>
                          {getTATStatusBadge(dispute)}
                        </TableCell>
                        <TableCell className="font-mono text-xs bg-muted px-2 py-1 rounded">
                          {dispute.transactionRRN}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleViewDispute(dispute)}
                              className="h-8 w-8 p-0"
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleUpdateDisputeStatus(dispute.disputeId, 
                                dispute.statusGroup === "Open" ? "Working" : 
                                dispute.statusGroup === "Working" ? "Closed" : "Open")}
                              className="h-8 w-8 p-0"
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteDispute(dispute.disputeId)}
                              className="h-8 w-8 p-0 text-red-600 hover:text-red-700"
                            >
                              <Trash2 className="h-4 w-4" />
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
      </Tabs>

      {/* Dispute Detail Modal */}
      <Dialog open={isDetailDialogOpen} onOpenChange={setIsDetailDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Dispute Details - {selectedDispute?.disputeId}
            </DialogTitle>
            <DialogDescription>
              Comprehensive view of dispute information and timeline
            </DialogDescription>
          </DialogHeader>
          
          {selectedDispute && (
            <div className="space-y-6">
              {/* Status Overview */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-muted/50 rounded-lg">
                  <div className="text-sm text-muted-foreground">Status</div>
                  <div className="font-semibold">{selectedDispute.statusGroup}</div>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <div className="text-sm text-muted-foreground">Stage</div>
                  <div className="font-semibold">{getStageName(selectedDispute.stageCode)}</div>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <div className="text-sm text-muted-foreground">TAT Days</div>
                  <div className="font-semibold">{selectedDispute.tatDays} days</div>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <div className="text-sm text-muted-foreground">TAT Status</div>
                  <div className="mt-1">{getTATStatusBadge(selectedDispute)}</div>
                </div>
              </div>

              {/* Dispute Information */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Dispute Information</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div>
                      <Label className="text-xs text-muted-foreground">Transaction Subtype</Label>
                      <div className="font-semibold">
                        <Badge variant="outline">{selectedDispute.txnSubtype}</Badge>
                      </div>
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground">Dispute Action</Label>
                      <div className="font-semibold">{selectedDispute.disputeCategory}</div>
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground">Reason Code</Label>
                      <div className="font-mono font-semibold bg-muted px-2 py-1 rounded text-sm">
                        {selectedDispute.reasonCode}
                      </div>
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground">Reason Description</Label>
                      <div className="text-sm">{selectedDispute.reasonDescription}</div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Transaction Details</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div>
                      <Label className="text-xs text-muted-foreground">RRN</Label>
                      <div className="font-mono font-semibold bg-muted px-2 py-1 rounded">
                        {selectedDispute.transactionRRN}
                      </div>
                    </div>
                    {selectedDispute.transactionAmount && (
                      <div>
                        <Label className="text-xs text-muted-foreground">Amount</Label>
                        <div className="font-semibold flex items-center gap-1">
                          <DollarSign className="h-4 w-4" />
                          ₹{selectedDispute.transactionAmount.toLocaleString('en-IN')}
                        </div>
                      </div>
                    )}
                    <div>
                      <Label className="text-xs text-muted-foreground">Transaction Date</Label>
                      <div className="font-semibold">
                        {new Date(selectedDispute.transactionDate).toLocaleDateString('en-IN')}
                      </div>
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground">Created</Label>
                      <div className="font-semibold">
                        {new Date(selectedDispute.createdAt).toLocaleString('en-IN')}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Timeline Placeholder */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Dispute Timeline</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-center text-muted-foreground py-8">
                    <Clock className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>Timeline feature coming soon</p>
                    <p className="text-sm">Track dispute progress and status changes</p>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}