import { useState } from "react";
import { Card, CardContent } from "../components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Upload, Loader2, CheckCircle } from "lucide-react";
import { useToast } from "../hooks/use-toast";
import { useMutation } from "@tanstack/react-query";
import { apiClient } from "../lib/api";
import { useDemoData } from "../contexts/DemoDataContext";
import { useNavigate } from "react-router-dom";

export default function FileUpload() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { triggerDemoData } = useDemoData();
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [cbsInward, setCbsInward] = useState<File | null>(null);
  const [cbsOutward, setCbsOutward] = useState<File | null>(null);
  const [cbsBalance, setCbsBalance] = useState("");
  const [cbsBalanceInput, setCbsBalanceInput] = useState("");
  const [switchFile, setSwitchFile] = useState<File | null>(null);
  const [npciFiles, setNpciFiles] = useState<Record<string, File>>({});
  const [selectedCycles, setSelectedCycles] = useState<Record<string, string>>({});
  const [currentStep, setCurrentStep] = useState("cbs");

  const uploadMutation = useMutation({
    mutationFn: async () => {
      // Validate mandatory fields
      if (!cbsInward || !cbsOutward || !switchFile) {
        throw new Error("Please select all required files (CBS Inward, CBS Outward, and Switch)");
      }

      // Only include NPCI files that were actually selected (not placeholders)
      const uploadData: any = {
        cbs_inward: cbsInward,
        cbs_outward: cbsOutward,
        switch: switchFile,
        cbs_balance: cbsBalance || cbsBalanceInput,
        transaction_date: date,
        selected_cycles: selectedCycles,
      };

      // Add optional NPCI files only if they were selected
      if (npciFiles.npci_inward) uploadData.npci_inward = npciFiles.npci_inward;
      if (npciFiles.npci_outward) uploadData.npci_outward = npciFiles.npci_outward;
      if (npciFiles.ntsl) uploadData.ntsl = npciFiles.ntsl;
      if (npciFiles.adjustment) uploadData.adjustment = npciFiles.adjustment;

      const uploadResult = await apiClient.uploadFiles(uploadData);

      // Automatically trigger reconciliation after successful upload
      await apiClient.runReconciliation();
      
      return uploadResult;
    },
    onSuccess: (data) => {
      const uploadedFilesList = data.uploaded_files || ['CBS Inward', 'CBS Outward', 'Switch'];
      const fileNames = uploadedFilesList
        .map(f => f.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()))
        .join(", ");

      // Trigger demo data when files are uploaded successfully
      triggerDemoData();

      toast({
        title: "Files uploaded successfully",
        description: `Run ID: ${data.run_id}. Uploaded: ${fileNames}. Demo data is now available.`,
      });

      // Dispatch event to refresh dashboard
      window.dispatchEvent(new CustomEvent('fileUploadComplete'));
      
      // Navigate to dashboard to show demo data
      setTimeout(() => {
        navigate('/');
      }, 1500);
      
      // Reset form
      setCbsInward(null);
      setCbsOutward(null);
      setSwitchFile(null);
      setCbsBalance("");
      setNpciFiles({});
    },
    onError: (error: any) => {
      toast({
        title: "Upload/Reconciliation failed",
        description: error.message || "An error occurred during upload or reconciliation",
        variant: "destructive",
      });
    },
  });

  const handleFileChange = (setter: (file: File | null) => void) => (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setter(e.target.files[0]);
    }
  };

  const handleNpciFileChange = (fileType: string) => (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setNpciFiles(prev => ({
        ...prev,
        [fileType]: e.target.files![0]
      }));
    }
  };

  const handleNextStep = () => {
    if (currentStep === "cbs" && (!cbsInward || !cbsOutward)) {
      toast({
        title: "Required files missing",
        description: "Please select both CBS Inward and CBS Outward files to proceed.",
        variant: "destructive",
      });
      return;
    }
    if (currentStep === "switch" && !switchFile) {
      toast({
        title: "Required file missing",
        description: "Please select the Switch file to proceed.",
        variant: "destructive",
      });
      return;
    }
    setCurrentStep(currentStep === "cbs" ? "switch" : "npci");
  };

  const handlePreviousStep = () => {
    setCurrentStep(currentStep === "switch" ? "cbs" : "switch");
  };

  const isUploading = uploadMutation.isPending;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">File Upload</h1>
        <p className="text-muted-foreground">
          {currentStep === "cbs" && "Step 1 of 3: Upload CBS and GL Files"}
          {currentStep === "switch" && "Step 2 of 3: Upload Switch File"}
          {currentStep === "npci" && "Step 3 of 3: Upload NPCI Files"}
        </p>
      </div>

      <Tabs value={currentStep} onValueChange={setCurrentStep} className="w-full">
        <TabsList className="bg-muted/30">
          <TabsTrigger
            value="cbs"
            className="data-[state=active]:bg-brand-blue data-[state=active]:text-primary-foreground"
          >
            CBS/ GL File
          </TabsTrigger>
          <TabsTrigger
            value="switch"
            className="data-[state=active]:bg-brand-blue data-[state=active]:text-primary-foreground"
          >
            Switch
          </TabsTrigger>
          <TabsTrigger
            value="npci"
            className="data-[state=active]:bg-brand-blue data-[state=active]:text-primary-foreground"
          >
            NPCI Files
          </TabsTrigger>
        </TabsList>
       
        {/* CBS/GL File Tab */}
        <TabsContent value="cbs">
          <div className="space-y-6 mt-6">
            <div className="text-sm text-muted-foreground">
              <p>Upload your CBS (Core Banking System) and GL (General Ledger) files for reconciliation.</p>
            </div>

            <Card className="shadow-lg">
              <CardContent className="space-y-8 pt-8">
                {/* CBS Inward File */}
                <div className="space-y-2">
                  <Label className="text-base font-semibold">Upload CBS Inward File *</Label>
                  <div className="flex gap-4 items-center">
                    <Button
                      variant="outline"
                      className="relative overflow-hidden rounded-full px-8"
                      onClick={() => document.getElementById('cbs-inward')?.click()}
                      disabled={isUploading}
                    >
                      <Upload className="w-4 h-4 mr-2" />
                      Browse
                    </Button>
                    <input
                      id="cbs-inward"
                      type="file"
                      className="hidden"
                      accept=".csv,.xlsx"
                      onChange={handleFileChange(setCbsInward)}
                    />
                    {cbsInward && (
                      <div className="flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-green-500" />
                        <span className="text-sm text-muted-foreground">{cbsInward.name}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* CBS Outward File */}
                <div className="space-y-2">
                  <Label className="text-base font-semibold">Upload CBS Outward File *</Label>
                  <div className="flex gap-4 items-center">
                    <Button
                      variant="outline"
                      className="relative overflow-hidden rounded-full px-8"
                      onClick={() => document.getElementById('cbs-outward')?.click()}
                      disabled={isUploading}
                    >
                      <Upload className="w-4 h-4 mr-2" />
                      Browse
                    </Button>
                    <input
                      id="cbs-outward"
                      type="file"
                      className="hidden"
                      accept=".csv,.xlsx"
                      onChange={handleFileChange(setCbsOutward)}
                    />
                    {cbsOutward && (
                      <div className="flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-green-500" />
                        <span className="text-sm text-muted-foreground">{cbsOutward.name}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* CBS Closing Balance */}
                <div className="space-y-2">
                  <Label className="text-base font-semibold">Enter CBS Closing Balance</Label>
                  <Input
                    type="text"
                    value={cbsBalance}
                    onChange={(e) => setCbsBalance(e.target.value)}
                    placeholder="Enter closing balance"
                    className="max-w-md"
                  />
                </div>

                <div className="flex justify-end pt-4">
                  <Button
                    className="rounded-full px-12 py-6 text-lg bg-brand-blue hover:bg-brand-mid shadow-lg hover:shadow-xl transition-all"
                    onClick={handleNextStep}
                    disabled={isUploading || !cbsInward || !cbsOutward}
                  >
                    Next
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Switch Tab */}
        <TabsContent value="switch">
          <div className="space-y-6 mt-6">
            <Card className="shadow-lg">
              <CardContent className="space-y-8 pt-8">
                <div className="space-y-2">
                  <Label className="text-base font-semibold">Upload Switch File *</Label>
                  <p className="text-sm text-muted-foreground">
                    Assumption is that the Inward & Outward Transactions are provided in a single file
                  </p>
                  <div className="flex gap-4 items-center">
                    <Button
                      variant="outline"
                      className="relative overflow-hidden rounded-full px-8"
                      onClick={() => document.getElementById('switch-file')?.click()}
                      disabled={isUploading}
                    >
                      <Upload className="w-4 h-4 mr-2" />
                      Browse
                    </Button>
                    <input
                      id="switch-file"
                      type="file"
                      className="hidden"
                      accept=".csv,.xlsx"
                      onChange={handleFileChange(setSwitchFile)}
                    />
                    {switchFile && (
                      <div className="flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-green-500" />
                        <span className="text-sm text-muted-foreground">{switchFile.name}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex justify-end pt-4">
                  <Button
                    variant="outline"
                    className="rounded-full px-8 mr-2"
                    onClick={handlePreviousStep}
                    disabled={isUploading}
                  >
                    Back
                  </Button>
                  <Button
                    className="rounded-full px-12 py-6 text-lg bg-brand-blue hover:bg-brand-mid shadow-lg hover:shadow-xl transition-all"
                    onClick={handleNextStep}
                    disabled={isUploading || !cbsInward || !cbsOutward || !switchFile}
                  >
                    Next
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* NPCI Files Tab - Secondary / Fall-back Upload Mode */}
        <TabsContent value="npci">
          <div className="space-y-6 mt-6">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <p className="text-sm text-amber-900">
                <strong>Secondary / Fall-back Upload Mode:</strong> Use this section to upload NPCI files as an alternative or backup method. NPCI files are optional and support multiple cycles (1-10).
              </p>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
              <p className="text-sm text-blue-900">
                <strong>Note:</strong> NPCI files are optional. You can upload any combination of NPCI Inward, NPCI Outward, NTSL, and Adjustment files.
              </p>
            </div>
            <Card className="shadow-lg">
              <CardContent className="space-y-8 pt-8">
                {/* NPCI Raw I/W File */}
                <div className="space-y-3">
                  <Label className="text-base font-semibold">NPCI Raw I/W File</Label>
                  <div className="flex gap-2 flex-wrap">
                    {Array.from({ length: 10 }, (_, i) => {
                      const cycleId = `${i + 1}C`;
                      const isSelected = selectedCycles.npci_inward === cycleId;
                      return (
                        <Button
                          key={i}
                          variant={isSelected ? "default" : "outline"}
                          size="sm"
                          className={`rounded-full ${isSelected ? 'bg-brand-blue text-white' : ''}`}
                          onClick={() => setSelectedCycles(prev => ({ ...prev, npci_inward: cycleId }))}
                        >
                          {cycleId}
                        </Button>
                      );
                    })}
                  </div>
                  {selectedCycles.npci_inward && (
                    <p className="text-sm text-muted-foreground">
                      Selected Cycle: {selectedCycles.npci_inward}
                    </p>
                  )}
                  <Button
                    variant="outline"
                    className="rounded-full px-8"
                    onClick={() => document.getElementById('npci-inward')?.click()}
                    disabled={isUploading}
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Browse
                  </Button>
                  <input
                    id="npci-inward"
                    type="file"
                    className="hidden"
                    accept=".csv,.xlsx"
                    onChange={handleNpciFileChange('npci_inward')}
                  />
                  {npciFiles.npci_inward && (
                    <div className="flex items-center gap-2 mt-2">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-muted-foreground">{npciFiles.npci_inward.name}</span>
                    </div>
                  )}
                </div>

                {/* NPCI Raw O/W File */}
                <div className="space-y-3">
                  <Label className="text-base font-semibold">NPCI Raw O/W File</Label>
                  <div className="flex gap-2 flex-wrap">
                    {Array.from({ length: 10 }, (_, i) => {
                      const cycleId = `${i + 1}C`;
                      const isSelected = selectedCycles.npci_outward === cycleId;
                      return (
                        <Button
                          key={i}
                          variant={isSelected ? "default" : "outline"}
                          size="sm"
                          className={`rounded-full ${isSelected ? 'bg-brand-blue text-white' : ''}`}
                          onClick={() => setSelectedCycles(prev => ({ ...prev, npci_outward: cycleId }))}
                        >
                          {cycleId}
                        </Button>
                      );
                    })}
                  </div>
                  {selectedCycles.npci_outward && (
                    <p className="text-sm text-muted-foreground">
                      Selected Cycle: {selectedCycles.npci_outward}
                    </p>
                  )}
                  <Button
                    variant="outline"
                    className="rounded-full px-8"
                    onClick={() => document.getElementById('npci-outward')?.click()}
                    disabled={isUploading}
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Browse
                  </Button>
                  <input
                    id="npci-outward"
                    type="file"
                    className="hidden"
                    accept=".csv,.xlsx"
                    onChange={handleNpciFileChange('npci_outward')}
                  />
                  {npciFiles.npci_outward && (
                    <div className="flex items-center gap-2 mt-2">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-muted-foreground">{npciFiles.npci_outward.name}</span>
                    </div>
                  )}
                </div>

                {/* NTSL File */}
                <div className="space-y-3">
                  <Label className="text-base font-semibold">NTSL File</Label>
                  <div className="text-sm text-muted-foreground mb-2">
                    Cycle for NTSL will be auto-detected from filename or file content.
                  </div>
                  <Button
                    variant="outline"
                    className="rounded-full px-8"
                    onClick={() => document.getElementById('ntsl-file')?.click()}
                    disabled={isUploading}
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Browse
                  </Button>
                  <input
                    id="ntsl-file"
                    type="file"
                    className="hidden"
                    accept=".csv,.xlsx"
                    onChange={handleNpciFileChange('ntsl')}
                  />
                  {npciFiles.ntsl && (
                    <div className="flex items-center gap-2 mt-2">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-muted-foreground">{npciFiles.ntsl.name}</span>
                    </div>
                  )}
                </div>

                {/* Adjustment File */}
                <div className="space-y-3">
                  <Label className="text-base font-semibold">Adjustment File</Label>
                  <div className="flex gap-2 flex-wrap">
                    {Array.from({ length: 10 }, (_, i) => {
                      const cycleId = `${i + 1}C`;
                      const isSelected = selectedCycles.adjustment === cycleId;
                      return (
                        <Button
                          key={i}
                          variant={isSelected ? "default" : "outline"}
                          size="sm"
                          className={`rounded-full ${isSelected ? 'bg-brand-blue text-white' : ''}`}
                          onClick={() => setSelectedCycles(prev => ({ ...prev, adjustment: cycleId }))}
                        >
                          {cycleId}
                        </Button>
                      );
                    })}
                  </div>
                  {selectedCycles.adjustment && (
                    <p className="text-sm text-muted-foreground">
                      Selected Cycle: {selectedCycles.adjustment}
                    </p>
                  )}
                  <Button
                    variant="outline"
                    className="rounded-full px-8"
                    onClick={() => document.getElementById('adjustment-file')?.click()}
                    disabled={isUploading}
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Browse
                  </Button>
                  <input
                    id="adjustment-file"
                    type="file"
                    className="hidden"
                    accept=".csv,.xlsx"
                    onChange={handleNpciFileChange('adjustment')}
                  />
                  {npciFiles.adjustment && (
                    <div className="flex items-center gap-2 mt-2">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span className="text-sm text-muted-foreground">{npciFiles.adjustment.name}</span>
                    </div>
                  )}
                </div>

                <div className="flex justify-end pt-4">
                  <Button
                    variant="outline"
                    className="rounded-full px-8 mr-2"
                    onClick={handlePreviousStep}
                    disabled={isUploading}
                  >
                    Back
                  </Button>
                  <Button
                    className="rounded-full px-12 py-6 text-lg bg-brand-blue hover:bg-brand-mid shadow-lg hover:shadow-xl transition-all"
                    onClick={() => uploadMutation.mutate()}
                    disabled={isUploading || !cbsInward || !cbsOutward || !switchFile}
                  >
                    {isUploading ? (
                      <>
                        <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                        Uploading...
                      </>
                    ) : (
                      "Upload Files"
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
