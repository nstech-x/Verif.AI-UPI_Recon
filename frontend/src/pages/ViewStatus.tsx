import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { AlertCircle, CheckCircle, Eye, RefreshCw } from "lucide-react";
import { apiClient } from "../lib/api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";

export default function ViewStatus() {
  const [uploadStatusData, setUploadStatusData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorDialogOpen, setErrorDialogOpen] = useState(false);
  const [selectedError, setSelectedError] = useState<any>(null);
  const [metadata, setMetadata] = useState<any>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  useEffect(() => {
    fetchUploadStatus();
  }, []);

  const fetchUploadStatus = async () => {
    try {
      setLoading(true);
      const metadata = await apiClient.getUploadMetadata();
      setMetadata(metadata);
      setLastUpdated(new Date().toLocaleString());

      console.log("Metadata response:", metadata);

      // Support both uploaded_files (array) and saved_files (object) formats
      const filesData = metadata.saved_files || metadata.uploaded_files || [];
      
      if (metadata.status === 'success' && filesData && (Array.isArray(filesData) && filesData.length > 0 || typeof filesData === 'object' && Object.keys(filesData).length > 0)) {
        const transformedData = transformRawDataToUploadStatus(filesData);
        setUploadStatusData(transformedData);
      } else {
        // Show empty state with proper structure
        setUploadStatusData(transformRawDataToUploadStatus({}));
      }
    } catch (error: any) {
      console.error("Error fetching upload status:", error);
      // Show empty state
      setUploadStatusData(transformRawDataToUploadStatus({}));
    } finally {
      setLoading(false);
    }
  };

  const transformRawDataToUploadStatus = (filesData: any) => {
    // Handle both array format (uploaded_files) and object format (saved_files)
    let fileList: string[] = [];
    let fileMap: Record<string, any> | null = null;

    if (Array.isArray(filesData)) {
      fileList = filesData;
    } else if (typeof filesData === 'object' && filesData !== null) {
      fileList = Object.keys(filesData);
      fileMap = filesData;
    }

    const normalizeFiles = (value: any): string[] => {
      if (!value) return [];
      if (Array.isArray(value)) return value.filter(Boolean);
      if (typeof value === "string") return [value];
      return [];
    };

    const count = (fileType: string) => {
      const normalizedFileType = fileType.toLowerCase().replace(/_/g, '');
      if (fileMap && fileType in fileMap) {
        const value = fileMap[fileType];
        if (Array.isArray(value)) {
          return value.length;
        }
        return value ? 1 : 0;
      }
      return fileList.some(file => {
        const normalizedFile = file.toLowerCase().replace(/_/g, '');
        return normalizedFile === normalizedFileType || file.toLowerCase().includes(fileType.toLowerCase());
      }) ? 1 : 0;
    };

    const filenamesFor = (fileType: string) => {
      if (fileMap && fileType in fileMap) {
        return normalizeFiles(fileMap[fileType]);
      }
      return fileList.filter(file => file.toLowerCase().includes(fileType.toLowerCase()));
    };

    return [
      {
        section: "CBS/ GL File",
        files: [
          { name: "CBS Inward File", key: "cbs_inward", required: true, uploaded: count('cbs_inward'), success: count('cbs_inward'), error: 0, errorDetails: null, filenames: filenamesFor('cbs_inward') },
          { name: "CBS Outward File", key: "cbs_outward", required: true, uploaded: count('cbs_outward'), success: count('cbs_outward'), error: 0, errorDetails: null, filenames: filenamesFor('cbs_outward') },
          { name: "Switch File", key: "switch", required: true, uploaded: count('switch'), success: count('switch'), error: 0, errorDetails: null, filenames: filenamesFor('switch') },
        ],
      },
      {
        section: "NPCI Files",
        files: [
          { name: "NPCI Inward Raw", key: "npci_inward", required: true, uploaded: count('npci_inward'), success: count('npci_inward'), error: 0, errorDetails: null, filenames: filenamesFor('npci_inward') },
          { name: "NPCI Outward Raw", key: "npci_outward", required: true, uploaded: count('npci_outward'), success: count('npci_outward'), error: 0, errorDetails: null, filenames: filenamesFor('npci_outward') },
        ],
      },
      {
        section: "Other Files",
        files: [
          { name: "NTSL", key: "ntsl", required: false, uploaded: count('ntsl'), success: count('ntsl'), error: 0, errorDetails: null, filenames: filenamesFor('ntsl') },
          { name: "Adjustment File", key: "adjustment", required: false, uploaded: count('adjustment'), success: count('adjustment'), error: 0, errorDetails: null, filenames: filenamesFor('adjustment') },
        ],
      },
    ];
  };

  const handleViewError = (errorDetails: any) => {
    setSelectedError(errorDetails);
    setErrorDialogOpen(true);
  };
  const requiredUploaded =
    uploadStatusData[0]?.files?.filter((f: any) => f.required).every((f: any) => f.success > 0) ?? false;
  const hasAnyUploads =
    uploadStatusData.some((section: any) => section.files.some((f: any) => f.uploaded > 0)) ?? false;

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">View Upload Status</h1>
          <p className="text-muted-foreground">Check the status of your file uploads</p>
          <div className="mt-2 text-xs text-muted-foreground">
            {metadata?.run_id ? (
              <span>Run ID: {metadata.run_id}</span>
            ) : (
              <span>No run data available</span>
            )}
            {metadata?.cycle_id ? <span className="ml-3">Cycle: {metadata.cycle_id}</span> : null}
            {metadata?.direction ? <span className="ml-3">Direction: {metadata.direction}</span> : null}
            {metadata?.run_date ? <span className="ml-3">Run Date: {metadata.run_date}</span> : null}
            {lastUpdated ? <span className="ml-3">Last Updated: {lastUpdated}</span> : null}
          </div>
        </div>
        <Button
          variant="outline"
          className="rounded-full gap-2"
          onClick={fetchUploadStatus}
          disabled={loading}
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {loading ? (
        <Card className="shadow-sm">
          <CardContent className="py-6 text-sm text-muted-foreground">
            Fetching latest upload status...
          </CardContent>
        </Card>
      ) : null}

      {/* Overall Status */}
      <div className="grid grid-cols-3 gap-6">
        <Card className={`shadow-lg ${requiredUploaded ? 'bg-gradient-to-br from-green-50 to-card' : 'bg-gradient-to-br from-red-50 to-card'}`}>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">CBS/ GL File</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {requiredUploaded ? (
                <>
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="text-lg font-semibold text-green-600">Successful</span>
                </>
              ) : (
                <>
                  <AlertCircle className="w-5 h-5 text-red-600" />
                  <span className="text-lg font-semibold text-red-600">Not Uploaded</span>
                </>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className={`shadow-lg ${uploadStatusData[0]?.files[2]?.success > 0 ? 'bg-gradient-to-br from-green-50 to-card' : 'bg-gradient-to-br from-red-50 to-card'}`}>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Switch</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {uploadStatusData[0]?.files[2]?.success > 0 ? (
                <>
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="text-lg font-semibold text-green-600">Successful</span>
                </>
              ) : (
                <>
                  <AlertCircle className="w-5 h-5 text-red-600" />
                  <span className="text-lg font-semibold text-red-600">Not Uploaded</span>
                </>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className={`shadow-lg ${uploadStatusData[1]?.files.some(f => f.success > 0) ? 'bg-gradient-to-br from-green-50 to-card' : 'bg-gradient-to-br from-red-50 to-card'}`}>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">NPCI Files</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {uploadStatusData[1]?.files.some(f => f.success > 0) ? (
                <>
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="text-lg font-semibold text-green-600">Successful</span>
                </>
              ) : (
                <>
                  <AlertCircle className="w-5 h-5 text-red-600" />
                  <span className="text-lg font-semibold text-red-600">Not Uploaded</span>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Table */}
      <Card className="shadow-lg">
        <CardHeader>
          <CardTitle>File Upload Details</CardTitle>
        </CardHeader>
        <CardContent>
          {!hasAnyUploads ? (
            <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
              No uploads found yet. Use the File Upload page to submit files and refresh this view.
            </div>
          ) : null}
          <div className="space-y-6">
            {uploadStatusData.map((section, idx) => (
              <div key={idx} className="space-y-3">
                <h3 className="font-semibold text-brand-blue">{section.section}</h3>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[32%]">File Type</TableHead>
                      <TableHead className="text-center w-[10%]">Required</TableHead>
                      <TableHead className="text-center w-[10%]">Uploaded</TableHead>
                      <TableHead className="text-center w-[10%]">Success</TableHead>
                      <TableHead className="text-center w-[10%]">Error</TableHead>
                      <TableHead className="w-[20%]">Latest Files</TableHead>
                      <TableHead className="text-center w-[8%]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {section.files.map((file, fileIdx) => (
                      <TableRow key={fileIdx}>
                        <TableCell className="font-medium">{file.name}</TableCell>
                        <TableCell className="text-center">
                          {file.required ? "Yes" : "Optional"}
                        </TableCell>
                        <TableCell className="text-center">{file.uploaded}</TableCell>
                        <TableCell className="text-center">
                          {file.success > 0 ? (
                            <div className="flex justify-center">
                              <Badge variant="default" className="bg-green-600 text-white">
                                {file.success}
                              </Badge>
                            </div>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-center">
                          {file.error > 0 ? (
                            <div className="flex justify-center">
                              <Badge variant="destructive">{file.error}</Badge>
                            </div>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {file.filenames && file.filenames.length > 0 ? (
                            <div className="space-y-1">
                              {file.filenames.slice(0, 3).map((name: string) => (
                                <div key={name} className="text-xs text-muted-foreground truncate">
                                  {name}
                                </div>
                              ))}
                              {file.filenames.length > 3 ? (
                                <div className="text-xs text-muted-foreground">+{file.filenames.length - 3} more</div>
                              ) : null}
                            </div>
                          ) : (
                            <span className="text-muted-foreground text-xs">No files</span>
                          )}
                        </TableCell>
                        <TableCell className="text-center">
                          {file.error > 0 ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="gap-2"
                              onClick={() => handleViewError(file.errorDetails || { message: "File upload failed. Please try again." })}
                            >
                              <Eye className="w-4 h-4" />
                              View Error
                            </Button>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              ))}
            </div>
        </CardContent>
      </Card>

      {/* Error Details Dialog */}
      <Dialog open={errorDialogOpen} onOpenChange={setErrorDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Error Details</DialogTitle>
            <DialogDescription>
              Information about the upload error
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm font-semibold text-red-900 mb-2">Error Message:</p>
              <p className="text-sm text-red-800">
                {selectedError?.message || "An error occurred during file upload"}
              </p>
            </div>
            {selectedError?.details && (
              <div className="p-4 bg-muted rounded-lg">
                <p className="text-sm font-semibold mb-2">Additional Details:</p>
                <pre className="text-xs whitespace-pre-wrap">
                  {JSON.stringify(selectedError.details, null, 2)}
                </pre>
              </div>
            )}
            <Button
              className="w-full"
              onClick={() => setErrorDialogOpen(false)}
            >
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
