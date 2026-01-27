import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { AlertCircle, CheckCircle, Loader2, Eye } from "lucide-react";
import { apiClient } from "../lib/api";
import { useToast } from "../hooks/use-toast";
import CycleSelector from "../components/CycleSelector";
import DirectionSelector from "../components/DirectionSelector";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";

export default function ViewStatus() {
  const { toast } = useToast();
  const [uploadStatusData, setUploadStatusData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedProcess, setSelectedProcess] = useState("inward");
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [selectedCycle, setSelectedCycle] = useState("all");
  const [errorDialogOpen, setErrorDialogOpen] = useState(false);
  const [selectedError, setSelectedError] = useState<any>(null);

  useEffect(() => {
    fetchUploadStatus();
  }, []);

  const fetchUploadStatus = async () => {
    try {
      setLoading(true);
      const metadata = await apiClient.getUploadMetadata();

      console.log("Metadata response:", metadata);

      // Support both uploaded_files (array) and saved_files (object) formats
      const filesData = metadata.uploaded_files || metadata.saved_files || [];
      
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

    if (Array.isArray(filesData)) {
      fileList = filesData;
    } else if (typeof filesData === 'object' && filesData !== null) {
      // Handle saved_files object format - explicitly look for npci_inward and npci_outward keys
      fileList = Object.keys(filesData);
    }

    // Check which files were actually uploaded by looking for exact key matches
    const has = (fileType: string) => {
      const normalizedFileType = fileType.toLowerCase().replace(/_/g, '');
      return fileList.some(file => {
        const normalizedFile = file.toLowerCase().replace(/_/g, '');
        return normalizedFile === normalizedFileType || file.toLowerCase().includes(fileType.toLowerCase());
      }) ? 1 : 0;
    };

    return [
      {
        section: "CBS/ GL File",
        files: [
          { name: "CBS Inward File", required: 1, uploaded: has('cbs_inward'), success: has('cbs_inward'), error: 0, errorDetails: null },
          { name: "CBS Outward File", required: 1, uploaded: has('cbs_outward'), success: has('cbs_outward'), error: 0, errorDetails: null },
          { name: "Switch File", required: 1, uploaded: has('switch'), success: has('switch'), error: 0, errorDetails: null },
        ],
      },
      {
        section: "NPCI Files",
        files: [
          { name: "NPCI Inward Raw", required: 1, uploaded: has('npci_inward'), success: has('npci_inward'), error: 0, errorDetails: null },
          { name: "NPCI Outward Raw", required: 1, uploaded: has('npci_outward'), success: has('npci_outward'), error: 0, errorDetails: null },
        ],
      },
      {
        section: "Other Files",
        files: [
          { name: "NTSL", required: 1, uploaded: has('ntsl'), success: has('ntsl'), error: 0, errorDetails: null },
          { name: "Adjustment File", required: 0, uploaded: has('adjustment'), success: has('adjustment'), error: 0, errorDetails: null },
        ],
      },
    ];
  };

  const handleViewError = (errorDetails: any) => {
    setSelectedError(errorDetails);
    setErrorDialogOpen(true);
  };
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">View Upload Status</h1>
        <p className="text-muted-foreground">Check the status of your file uploads</p>
      </div>

     

      {/* Overall Status */}
      <div className="grid grid-cols-3 gap-6">
        <Card className={`shadow-lg ${uploadStatusData[0]?.files.some(f => f.success > 0) ? 'bg-gradient-to-br from-green-50 to-card' : 'bg-gradient-to-br from-red-50 to-card'}`}>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">CBS/ GL File</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {uploadStatusData[0]?.files.some(f => f.success > 0) ? (
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
          <div className="space-y-6">
            {uploadStatusData.map((section, idx) => (
              <div key={idx} className="space-y-3">
                <h3 className="font-semibold text-brand-blue">{section.section}</h3>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[40%]">File Name</TableHead>
                      <TableHead className="text-center w-[12%]">Required</TableHead>
                      <TableHead className="text-center w-[12%]">Uploaded</TableHead>
                      <TableHead className="text-center w-[12%]">Success</TableHead>
                      <TableHead className="text-center w-[12%]">Error</TableHead>
                      <TableHead className="text-center w-[12%]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {section.files.map((file, fileIdx) => (
                      <TableRow key={fileIdx}>
                        <TableCell className="font-medium">{file.name}</TableCell>
                        <TableCell className="text-center">
                          {file.required === 0 ? "NA" : file.required}
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