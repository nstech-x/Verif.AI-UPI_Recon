import { useState } from "react";
import { Button } from "../components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Download, Loader2, Plus, FileText, Calendar } from "lucide-react";
import { apiClient } from "../lib/api";
import { useToast } from "../hooks/use-toast";

// Report category definitions
interface ReportDefinition {
  id: string;
  name: string;
  description: string;
  format: string;
}

interface ReportCategory {
  name: string;
  description: string;
  subcategories?: Record<string, { name: string; description: string; reports: ReportDefinition[] }>;
  reports?: ReportDefinition[];
}

const REPORT_CATEGORIES: Record<string, ReportCategory> = {
  listing: {
    name: "Listing Reports",
    description: "Raw ingestion listings from CBS, Switch, and NPCI sources",
    reports: [
      {
        id: "cbs_beneficiary_listing",
        name: "CBS Beneficiary Listing (Inward)",
        description: "Raw CBS inward listing (beneficiary)",
        format: "CSV",
      },
      {
        id: "cbs_remitter_listing",
        name: "CBS Remitter Listing (Outward)",
        description: "Raw CBS outward listing (remitter)",
        format: "CSV",
      },
      {
        id: "switch_listing_inward",
        name: "Switch Listing (Inward)",
        description: "Raw switch inward transactions",
        format: "CSV",
      },
      {
        id: "switch_listing_outward",
        name: "Switch Listing (Outward)",
        description: "Raw switch outward transactions",
        format: "CSV",
      },
      {
        id: "npci_beneficiary_listing",
        name: "NPCI Beneficiary Listing (Inward)",
        description: "Raw NPCI inward transactions",
        format: "CSV",
      },
      {
        id: "npci_remitter_listing",
        name: "NPCI Remitter Listing (Outward)",
        description: "Raw NPCI outward transactions",
        format: "CSV",
      },
    ],
  },
  reconciliation: {
    name: "Reconciliation Reports",
    description: "Matched/Unmatched and operational reconciliation outputs",
    reports: [
      {
        id: "matched_transactions",
        name: "Matched Transactions",
        description: "All successfully matched transactions",
        format: "CSV",
      },
      {
        id: "unmatched_transactions",
        name: "Unmatched Transactions",
        description: "All unmatched transactions and exceptions",
        format: "CSV",
      },
      {
        id: "adjustment_report_listing",
        name: "Adjustment Report Listing",
        description: "Adjustment candidates and exception listing",
        format: "CSV",
      },
      {
        id: "switch_status_update",
        name: "Switch Status Update",
        description: "Status update file for switch operations",
        format: "CSV",
      },
    ],
  },
  ttum_annexure: {
    name: "TTUM & Annexure",
    description: "TTUM listings and NPCI bulk upload formats",
    reports: [
      {
        id: "ttum_receivable_inward",
        name: "TTUM Listing - Receivable / Inward GL",
        description: "TTUM candidates for inward GL receivables",
        format: "CSV",
      },
      {
        id: "ttum_payable_outward",
        name: "TTUM Listing - Payable / Outward GL",
        description: "TTUM candidates for outward GL payables",
        format: "CSV",
      },
      {
        id: "annexure_iv_tcc_ret",
        name: "NPCI Bulk Upload - Time out (TCC & RET Cases)",
        description: "Annexure IV format for TCC and RET cases",
        format: "CSV",
      },
      {
        id: "annexure_iv_drc_rrc",
        name: "NPCI Bulk Upload - DRC & RRC",
        description: "Annexure IV format for DRC/RRC cases",
        format: "CSV",
      },
      {
        id: "adjustment_report",
        name: "Adjustment Report",
        description: "Adjustment summary report (Annexure III)",
        format: "CSV",
      },
    ],
  },
  settlement_ntsl: {
    name: "Settlement & NTSL",
    description: "NTSL settlement TTUM and settlement extracts",
    reports: [
      {
        id: "ntsl_settlement_ttum_sponsor",
        name: "NTSL Settlement TTUM (Sponsor Bank)",
        description: "Sponsor bank TTUM listing for NTSL settlement",
        format: "CSV",
      },
      {
        id: "ntsl_settlement_ttum_submember",
        name: "NTSL Settlement TTUM (Sub-Member Bank)",
        description: "Sub-member bank TTUM listing for NTSL settlement",
        format: "CSV",
      },
      {
        id: "monthly_settlement_ntsl",
        name: "Monthly Settlement Report - NTSL Extract",
        description: "Monthly NTSL settlement extract",
        format: "CSV",
      },
    ],
  },
  compliance: {
    name: "Compliance & MIS",
    description: "MIS, GL justification, disputes, and RBI reporting",
    reports: [
      {
        id: "gl_justification",
        name: "GL Justification",
        description: "GL justification / proofing report",
        format: "CSV",
      },
      {
        id: "mis_daily",
        name: "MIS (Daily) - Interchange & GST",
        description: "Daily MIS report (Interchange & GST)",
        format: "CSV",
      },
      {
        id: "mis_weekly",
        name: "MIS (Weekly) - Interchange & GST",
        description: "Weekly MIS report (Interchange & GST)",
        format: "CSV",
      },
      {
        id: "mis_monthly",
        name: "MIS (Monthly) - Interchange & GST",
        description: "Monthly MIS report (Interchange & GST)",
        format: "CSV",
      },
      {
        id: "income_expense_datewise",
        name: "Datewise Income - Expense Report",
        description: "Datewise income and expense summary",
        format: "CSV",
      },
      {
        id: "dispute_tracker",
        name: "Dispute Tracker",
        description: "Dispute tracking report",
        format: "CSV",
      },
      {
        id: "rbi_reporting",
        name: "RBI Reporting",
        description: "Regulatory summary for RBI reporting",
        format: "CSV",
      },
    ],
  },
};

export default function Reports() {
  const { toast } = useToast();
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [selectedSubcategory, setSelectedSubcategory] = useState<string>("");
  const [selectedReport, setSelectedReport] = useState<string>("");
  const [dateRange, setDateRange] = useState<string>("today");
  const [isDownloading, setIsDownloading] = useState(false);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  
  // Create Report Type form state
  const [newReport, setNewReport] = useState({
    name: "",
    category: "",
    format: "CSV",
    description: "",
  });

  // Get current category data
  const currentCategory = selectedCategory ? REPORT_CATEGORIES[selectedCategory] : null;
  const hasSubcategories = currentCategory?.subcategories !== undefined;
  const currentSubcategory = hasSubcategories && selectedSubcategory 
    ? currentCategory.subcategories![selectedSubcategory] 
    : null;

  // Get available reports based on selection
  const availableReports = currentSubcategory?.reports || currentCategory?.reports || [];
  const selectedReportData = availableReports.find((r) => r.id === selectedReport);

  const handleDownload = async () => {
    if (!selectedReportData) {
      toast({
        title: "Error",
        description: "Please select a report to download",
        variant: "destructive",
      });
      return;
    }

    try {
      setIsDownloading(true);

      const reportKeyMapping: Record<string, string> = {
        cbs_beneficiary_listing: "download/cbs_beneficiary_listing",
        cbs_remitter_listing: "download/cbs_remitter_listing",
        switch_listing_inward: "download/switch_listing_inward",
        switch_listing_outward: "download/switch_listing_outward",
        npci_beneficiary_listing: "download/npci_beneficiary_listing",
        npci_remitter_listing: "download/npci_remitter_listing",
        adjustment_report_listing: "download/adjustment_report_listing",
        matched_transactions: "download/matched_transactions",
        unmatched_transactions: "download/unmatched_transactions",
        ttum_receivable_inward: "download/ttum_receivable_inward",
        ttum_payable_outward: "download/ttum_payable_outward",
        switch_status_update: "download/switch_status_update",
        ntsl_settlement_ttum_sponsor: "download/ntsl_settlement_ttum_sponsor",
        ntsl_settlement_ttum_submember: "download/ntsl_settlement_ttum_submember",
        gl_justification: "download/gl_justification",
        annexure_iv_tcc_ret: "download/annexure_iv_tcc_ret",
        annexure_iv_drc_rrc: "download/annexure_iv_drc_rrc",
        adjustment_report: "download/adjustment_report",
        mis_daily: "download/mis_daily",
        mis_weekly: "download/mis_weekly",
        mis_monthly: "download/mis_monthly",
        income_expense_datewise: "download/income_expense_datewise",
        monthly_settlement_ntsl: "download/monthly_settlement_ntsl",
        dispute_tracker: "download/dispute_tracker",
        rbi_reporting: "download/rbi_reporting",
      };

      const endpoint = reportKeyMapping[selectedReportData.id];
      if (!endpoint) {
        toast({
          title: "File Not Found",
          description: "The requested report is not available in the backend.",
          variant: "destructive",
        });
        return;
      }

      const formatDate = (value: Date) => value.toISOString().slice(0, 10);
      const now = new Date();
      let dateFrom = now;
      let dateTo = now;
      if (dateRange === "week") {
        dateFrom = new Date(now);
        dateFrom.setDate(now.getDate() - 6);
      } else if (dateRange === "month") {
        dateFrom = new Date(now.getFullYear(), now.getMonth(), 1);
      } else if (dateRange === "custom") {
        dateFrom = new Date(now);
        dateFrom.setDate(now.getDate() - 30);
      }

      const params: Record<string, string> = {};
      if (["mis_daily", "mis_weekly", "mis_monthly", "income_expense_datewise"].includes(selectedReportData.id)) {
        params.date_from = formatDate(dateFrom);
        params.date_to = formatDate(dateTo);
      }

      const response = await apiClient.downloadReport(endpoint, Object.keys(params).length ? params : undefined);

      const disposition = response.headers["content-disposition"] as string | undefined;
      const filenameMatch = disposition?.match(/filename="?([^"]+)"?/i);
      const fallbackName = `${selectedReportData.id}.${selectedReportData.format.toLowerCase()}`;
      const filename = filenameMatch?.[1] || fallbackName;

      apiClient.triggerFileDownload(response.data, filename);

      toast({
        title: "Download Started",
        description: `${filename} is being downloaded from the backend.`,
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to download report from backend.",
        variant: "destructive",
      });
    } finally {
      setIsDownloading(false);
    }
  };


  const handleCreateReportType = () => {
    // Demo mode - just show success toast
    toast({
      title: "Report Type Saved (Demo Mode)",
      description: `Report type "${newReport.name}" has been saved for demonstration purposes.`,
    });
    
    // Reset form and close dialog
    setNewReport({ name: "", category: "", format: "CSV", description: "" });
    setShowCreateDialog(false);
  };

  // Reset subcategory and report when category changes
  const handleCategoryChange = (value: string) => {
    setSelectedCategory(value);
    setSelectedSubcategory("");
    setSelectedReport("");
  };

  // Reset report when subcategory changes
  const handleSubcategoryChange = (value: string) => {
    setSelectedSubcategory(value);
    setSelectedReport("");
  };

  return (
    <div className="p-6 space-y-6">
      {/* Lean Header - Single Row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Reports</h1>
          <p className="text-sm text-muted-foreground">Generate and download reconciliation reports</p>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Date Range Selector */}
          <Select value={dateRange} onValueChange={setDateRange}>
            <SelectTrigger className="w-[140px] h-9">
              <Calendar className="w-4 h-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="today">Today</SelectItem>
              <SelectItem value="week">This Week</SelectItem>
              <SelectItem value="month">This Month</SelectItem>
              <SelectItem value="custom">Custom Range</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Main Content - Dropdown-Driven Selection */}
      <div className="border rounded-lg bg-card">
        <div className="p-6 space-y-6">
          {/* Step 1: Report Category */}
          <div className="space-y-2">
            <Label htmlFor="category" className="text-sm font-medium">
              Report Category
            </Label>
            <Select value={selectedCategory} onValueChange={handleCategoryChange}>
              <SelectTrigger id="category" className="w-full">
                <SelectValue placeholder="Select report category" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(REPORT_CATEGORIES).map(([key, cat]) => (
                  <SelectItem key={key} value={key}>
                    {cat.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {currentCategory && (
              <p className="text-sm text-muted-foreground">{currentCategory.description}</p>
            )}
          </div>

          {/* Step 2: Sub-Category (Conditional) */}
          {hasSubcategories && selectedCategory && (
            <div className="space-y-2">
              <Label htmlFor="subcategory" className="text-sm font-medium">
                Sub-Category
              </Label>
              <Select value={selectedSubcategory} onValueChange={handleSubcategoryChange}>
                <SelectTrigger id="subcategory" className="w-full">
                  <SelectValue placeholder="Select sub-category" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(currentCategory.subcategories!).map(([key, subcat]) => (
                    <SelectItem key={key} value={key}>
                      {subcat.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {currentSubcategory && (
                <p className="text-sm text-muted-foreground">{currentSubcategory.description}</p>
              )}
            </div>
          )}

          {/* Step 3: Report Type */}
          {availableReports.length > 0 && (
            <div className="space-y-2">
              <Label htmlFor="report" className="text-sm font-medium">
                Report Type
              </Label>
              <Select value={selectedReport} onValueChange={setSelectedReport}>
                <SelectTrigger id="report" className="w-full">
                  <SelectValue placeholder="Select specific report" />
                </SelectTrigger>
                <SelectContent>
                  {availableReports.map((report) => (
                    <SelectItem key={report.id} value={report.id}>
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4" />
                        <span>{report.name}</span>
                        <span className="text-xs text-muted-foreground">({report.format})</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedReportData && (
                <p className="text-sm text-muted-foreground">{selectedReportData.description}</p>
              )}
            </div>
          )}

          {/* Download Button */}
          <div className="flex items-center gap-3 pt-2">
            <Button
              onClick={handleDownload}
              disabled={!selectedReport || isDownloading}
              className="bg-brand-blue hover:bg-brand-mid text-white"
            >
              {isDownloading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Downloading...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4 mr-2" />
                  Download Report
                </>
              )}
            </Button>

            <Button
              variant="outline"
              onClick={() => setShowCreateDialog(true)}
              className="border-brand-blue text-brand-blue hover:bg-brand-light"
            >
              <Plus className="w-4 h-4 mr-2" />
              Create Report Type
            </Button>
          </div>
        </div>
      </div>

      {/* Create Report Type Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Create New Report Type</DialogTitle>
            <DialogDescription>
              Define a new report type for future use. This is for demonstration purposes only.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="report-name">Report Name</Label>
              <Input
                id="report-name"
                placeholder="e.g., Custom Settlement Report"
                value={newReport.name}
                onChange={(e) => setNewReport({ ...newReport, name: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="report-category">Category</Label>
              <Select
                value={newReport.category}
                onValueChange={(value) => setNewReport({ ...newReport, category: value })}
              >
                <SelectTrigger id="report-category">
                  <SelectValue placeholder="Select category" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(REPORT_CATEGORIES).map(([key, cat]) => (
                    <SelectItem key={key} value={key}>
                      {cat.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="report-format">File Format</Label>
              <Select
                value={newReport.format}
                onValueChange={(value) => setNewReport({ ...newReport, format: value })}
              >
                <SelectTrigger id="report-format">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="CSV">CSV</SelectItem>
                  <SelectItem value="XLSX">XLSX</SelectItem>
                  <SelectItem value="PDF">PDF</SelectItem>
                  <SelectItem value="ZIP">ZIP</SelectItem>
                  <SelectItem value="JSON">JSON</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="report-description">Description</Label>
              <Textarea
                id="report-description"
                placeholder="Describe the purpose and content of this report..."
                value={newReport.description}
                onChange={(e) => setNewReport({ ...newReport, description: e.target.value })}
                rows={3}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateReportType}
              disabled={!newReport.name || !newReport.category}
              className="bg-brand-blue hover:bg-brand-mid text-white"
            >
              Save Report Type
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
