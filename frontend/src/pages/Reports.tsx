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
import { AxiosResponse } from "axios";

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
    description: "Pre-Reconciliation Listing - Raw ingestion files from 6 core data sources",
    reports: [
      {
        id: "cbs_beneficiary",
        name: "CBS Beneficiary (Raw)",
        description: "Raw beneficiary data from Core Banking System",
        format: "CSV",
      },
      {
        id: "cbs_remitter",
        name: "CBS Remitter (Raw)",
        description: "Raw remitter data from Core Banking System",
        format: "CSV",
      },
      {
        id: "switch_inward",
        name: "Switch Inward (Raw)",
        description: "Raw inward transaction data from Switch",
        format: "CSV",
      },
      {
        id: "switch_outward",
        name: "Switch Outward (Raw)",
        description: "Raw outward transaction data from Switch",
        format: "CSV",
      },
      {
        id: "npci_inward",
        name: "NPCI Inward (Raw)",
        description: "Raw inward transaction data from NPCI",
        format: "CSV",
      },
      {
        id: "npci_outward",
        name: "NPCI Outward (Raw)",
        description: "Raw outward transaction data from NPCI",
        format: "CSV",
      },
    ],
  },
  reconciliation: {
    name: "Reconciliation Reports",
    description: "Reconciliation reports with 3 comparison pairs plus Hanging Transactions",
    subcategories: {
      inward: {
        name: "Inward Direction",
        description: "Credit/Inward transactions reconciliation",
        reports: [
          {
            id: "gl_switch_matched_inward",
            name: "GL vs. Switch - Matched",
            description: "Inward transactions matched between GL and Switch",
            format: "CSV",
          },
          {
            id: "gl_switch_unmatched_inward",
            name: "GL vs. Switch - Unmatched (with Ageing)",
            description: "Inward transactions unmatched between GL and Switch with aging",
            format: "CSV",
          },
          {
            id: "switch_network_matched_inward",
            name: "Switch vs. Network - Matched",
            description: "Inward transactions matched between Switch and Network",
            format: "CSV",
          },
          {
            id: "switch_network_unmatched_inward",
            name: "Switch vs. Network - Unmatched (with Ageing)",
            description: "Inward transactions unmatched between Switch and Network",
            format: "CSV",
          },
          {
            id: "gl_network_matched_inward",
            name: "GL vs. Network - Matched",
            description: "Inward transactions matched between GL and Network",
            format: "CSV",
          },
          {
            id: "gl_network_unmatched_inward",
            name: "GL vs. Network - Unmatched (with Ageing)",
            description: "Inward transactions unmatched between GL and Network",
            format: "CSV",
          },
          {
            id: "hanging_transactions_inward",
            name: "Hanging Transactions",
            description: "Inward transactions stuck in intermediate state",
            format: "CSV",
          },
        ],
      },
      outward: {
        name: "Outward Direction",
        description: "Debit/Outward transactions reconciliation",
        reports: [
          {
            id: "gl_switch_matched_outward",
            name: "GL vs. Switch - Matched",
            description: "Outward transactions matched between GL and Switch",
            format: "CSV",
          },
          {
            id: "gl_switch_unmatched_outward",
            name: "GL vs. Switch - Unmatched (with Ageing)",
            description: "Outward transactions unmatched between GL and Switch",
            format: "CSV",
          },
          {
            id: "switch_network_matched_outward",
            name: "Switch vs. Network - Matched",
            description: "Outward transactions matched between Switch and Network",
            format: "CSV",
          },
          {
            id: "switch_network_unmatched_outward",
            name: "Switch vs. Network - Unmatched (with Ageing)",
            description: "Outward transactions unmatched between Switch and Network",
            format: "CSV",
          },
          {
            id: "gl_network_matched_outward",
            name: "GL vs. Network - Matched",
            description: "Outward transactions matched between GL and Network",
            format: "CSV",
          },
          {
            id: "gl_network_unmatched_outward",
            name: "GL vs. Network - Unmatched (with Ageing)",
            description: "Outward transactions unmatched between GL and Network",
            format: "CSV",
          },
          {
            id: "hanging_transactions_outward",
            name: "Hanging Transactions",
            description: "Outward transactions stuck in intermediate state",
            format: "CSV",
          },
        ],
      },
    },
  },
  ttum_annexure: {
    name: "TTUM & Annexure",
    description: "TTUM consolidated report and Annexure files (I-IV)",
    subcategories: {
      consolidated: {
        name: "Consolidated TTUM",
        description: "Complete TTUM report package",
        reports: [
          {
            id: "ttum_consolidated",
            name: "Consolidated TTUM Report",
            description: "Complete TTUM with Refund, Recovery, Auto-credit, etc.",
            format: "ZIP",
          },
        ],
      },
      annexures: {
        name: "Annexure Files",
        description: "Individual annexure reports",
        reports: [
          {
            id: "annexure_i",
            name: "Annexure I (Raw)",
            description: "Raw Annexure I data for detailed review",
            format: "CSV",
          },
          {
            id: "annexure_ii",
            name: "Annexure II (Raw)",
            description: "Raw Annexure II data for detailed review",
            format: "CSV",
          },
          {
            id: "annexure_iii",
            name: "Annexure III (Adjustment Report)",
            description: "Adjustment report with reconciliation details",
            format: "CSV",
          },
          {
            id: "annexure_iv",
            name: "Annexure IV (Bulk Upload)",
            description: "Bulk upload format for system import",
            format: "XLSX",
          },
        ],
      },
    },
  },
  rbi_regulatory: {
    name: "RBI / Regulatory Reports",
    description: "Regulatory compliance and RBI submission reports",
    subcategories: {
      settlement: {
        name: "Settlement Reports",
        description: "Daily settlement and clearing reports",
        reports: [
          {
            id: "daily_settlement",
            name: "Daily Settlement Report",
            description: "Daily UPI settlement report for RBI submission",
            format: "PDF",
          },
          {
            id: "npci_clearing",
            name: "NPCI Clearing Report",
            description: "NPCI clearing summary with net positions",
            format: "XLSX",
          },
        ],
      },
      aging: {
        name: "Aging Reports",
        description: "Transaction aging analysis",
        reports: [
          {
            id: "unmatched_aging",
            name: "Unmatched Transactions Aging",
            description: "Age-wise breakup of unmatched transactions",
            format: "CSV",
          },
        ],
      },
      disputes: {
        name: "Disputes & Chargebacks",
        description: "Dispute and chargeback tracking",
        reports: [
          {
            id: "dispute_summary",
            name: "Dispute Summary Report",
            description: "Summary of open, working, and closed disputes",
            format: "CSV",
          },
        ],
      },
    },
  },
  legacy: {
    name: "Legacy Reports",
    description: "Standard reconciliation reports for backward compatibility",
    reports: [
      {
        id: "matched_json",
        name: "Matched Transactions (JSON)",
        description: "All successfully matched transactions",
        format: "JSON",
      },
      {
        id: "unmatched_json",
        name: "Unmatched Transactions (JSON)",
        description: "Transactions that couldn't be matched",
        format: "JSON",
      },
      {
        id: "summary_json",
        name: "Reconciliation Summary (JSON)",
        description: "Complete summary with statistics",
        format: "JSON",
      },
      {
        id: "matched_csv",
        name: "Matched Transactions (CSV)",
        description: "Matched transactions in CSV format",
        format: "CSV",
      },
      {
        id: "unmatched_csv",
        name: "Unmatched Transactions (CSV)",
        description: "Unmatched transactions in CSV format",
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

      // S3 Root URLs
      const S3_REPORTS_URL = "https://nstechx.s3.ap-south-1.amazonaws.com/reports/";
      const S3_TTUM_URL = "https://nstechx.s3.ap-south-1.amazonaws.com/ttum/";
      const S3_ROOT_URL = "https://nstechx.s3.ap-south-1.amazonaws.com/";

      // Mapping of Report IDs to their exact S3 filenames
      const s3FileMapping: Record<string, { url: string; name: string }> = {
        // Reconciliation Reports
        "gl_network_matched_inward": { url: S3_REPORTS_URL, name: "GL_vs_NPCI_Inward.xlsx" },
        "gl_network_matched_outward": { url: S3_REPORTS_URL, name: "GL_vs_NPCI_Outward.xlsx" },
        "gl_switch_matched_inward": { url: S3_REPORTS_URL, name: "GL_vs_Switch_Inward.xlsx" },
        "gl_switch_matched_outward": { url: S3_REPORTS_URL, name: "GL_vs_Switch_Outward.xlsx" },
        "switch_network_matched_inward": { url: S3_REPORTS_URL, name: "Switch_vs_NPCI_Inward.xlsx" },
        "switch_network_matched_outward": { url: S3_REPORTS_URL, name: "Switch_vs_NPCI_Outward.xlsx" },
        
        // Annexures
        "annexure_i": { url: S3_REPORTS_URL, name: "ANNEXURE_I.xlsx" },
        "annexure_ii": { url: S3_REPORTS_URL, name: "ANNEXURE_II.xlsx" },
        "annexure_iii": { url: S3_REPORTS_URL, name: "ANNEXURE_III.xlsx" },
        "annexure_iv": { url: S3_REPORTS_URL, name: "ANNEXURE_IV.xlsx" },
        
        // Exceptions & Aging
        "unmatched_aging": { url: S3_REPORTS_URL, name: "Unmatched_Inward_Ageing.xlsx" },
        "ttum_candidates": { url: S3_REPORTS_URL, name: "ttum_candidates.xlsx" },
        
        // TTUM Packages
        "ttum_consolidated": { url: S3_TTUM_URL, name: "ttum_RUN_20260108_023831.zip" }
      };

      const fileInfo = s3FileMapping[selectedReportData.id];

      if (fileInfo) {
        const downloadUrl = `${fileInfo.url}${fileInfo.name}`;
        
        // Create temporary link to trigger download
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.setAttribute("download", fileInfo.name);
        link.setAttribute("target", "_blank");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        toast({
          title: "Download Started",
          description: `${fileInfo.name} is being downloaded from S3.`,
        });
      } else {
        toast({
          title: "File Not Found",
          description: "The requested report is not available in the demo S3 bucket.",
          variant: "destructive",
        });
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to connect to S3 storage.",
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