import { useState } from "react";
import { Card, CardContent } from "../components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Upload, Loader2, CheckCircle } from "lucide-react";
import { useToast } from "../hooks/use-toast";
import { useMutation } from "@tanstack/react-query";
import { apiClient } from "../lib/api";
import { useDemoData } from "../contexts/DemoDataContext";
import { Link, useNavigate } from "react-router-dom";

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
  const [npciFiles, setNpciFiles] = useState<Record<string, File[]>>({});
  const [currentStep, setCurrentStep] = useState("cbs");

  const uploadMutation = useMutation({
    mutationFn: async () => {
      // Validate mandatory fields
      if (!cbsInward || !cbsOutward || !switchFile) {
        throw new Error("Please select all required files (CBS Inward, CBS Outward, and Switch)");
      }

      const uploadData: any = {
        cbs_inward: cbsInward,
        cbs_outward: cbsOutward,
        switch: switchFile,
        cbs_balance: cbsBalance || cbsBalanceInput,
        transaction_date: date,
      };

      // Add optional NPCI files only if they were selected
      if (npciFiles.npci_inward?.length) uploadData.npci_inward = npciFiles.npci_inward;
      if (npciFiles.npci_outward?.length) uploadData.npci_outward = npciFiles.npci_outward;
      if (npciFiles.ntsl?.length) uploadData.ntsl = npciFiles.ntsl;
      if (npciFiles.adjustment?.length) uploadData.adjustment = npciFiles.adjustment;

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
    if (!e.target.files || e.target.files.length === 0) return;

    const files = Array.from(e.target.files);
    const accepted: File[] = [];

    const validateFilename = (file: File): boolean => {
      const name = (file.name || "").toLowerCase();
      const cycleMatch = name.match(/cycle\s*0*(\d{1,2})/);
      const typeMatch = name.match(/(?:^|[_-])(inward|outward)(?:[_-]|$)/);
      const dateMatch = name.match(/(\d{2})(\d{2})(\d{4})/);

      if (!cycleMatch || !typeMatch || !dateMatch) {
        toast({
          title: "Invalid filename",
          description: "Filename must follow pattern cycle<no>_(inward|outward)_DDMMYYYY[_suffix]. File rejected.",
          variant: "destructive",
        });
        return false;
      }

      const cycleNum = parseInt(cycleMatch[1], 10);
      if (cycleNum < 1 || cycleNum > 10) {
        toast({
          title: "Invalid cycle number",
          description: "Cycle number in filename must be between 1 and 10. File rejected.",
          variant: "destructive",
        });
        return false;
      }

      const dd = parseInt(dateMatch[1], 10);
      const mm = parseInt(dateMatch[2], 10);
      const yyyy = parseInt(dateMatch[3], 10);

      const parsedDate = new Date(yyyy, mm - 1, dd);
      const isValidDate = parsedDate.getDate() === dd && parsedDate.getMonth() === mm - 1 && parsedDate.getFullYear() === yyyy;
      if (!isValidDate) {
        toast({
          title: "Invalid file date",
          description: `The date in file name (${String(dd).padStart(2, '0')}-${String(mm).padStart(2, '0')}-${yyyy}) is not a valid date. File rejected.`,
          variant: "destructive",
        });
        return false;
      }

      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      if (parsedDate.getTime() !== today.getTime()) {
        toast({
          title: "Invalid file date",
          description: `The date in file name (${String(dd).padStart(2, '0')}-${String(mm).padStart(2, '0')}-${yyyy}) must be today's date. File rejected.`,
          variant: "destructive",
        });
        return false;
      }

      if (fileType === 'npci_inward' && typeMatch[1] !== 'inward') {
        toast({
          title: "Invalid file direction",
          description: "NPCI inward files must include 'inward' in the filename. File rejected.",
          variant: "destructive",
        });
        return false;
      }

      if (fileType === 'npci_outward' && typeMatch[1] !== 'outward') {
        toast({
          title: "Invalid file direction",
          description: "NPCI outward files must include 'outward' in the filename. File rejected.",
          variant: "destructive",
        });
        return false;
      }

      return true;
    };

    files.forEach((file) => {
      if (validateFilename(file)) {
        accepted.push(file);
      }
    });

    if (accepted.length === 0) return;

    setNpciFiles(prev => ({
      ...prev,
      [fileType]: accepted
    }));
  };

  const handleNextStep = () => {
    if (currentStep === "cbs" && (!cbsInward || !cbsOutward || !switchFile)) {
      toast({
        title: "Required files missing",
        description: "Please select CBS Inward, CBS Outward and Switch files to proceed.",
        variant: "destructive",
      });
      return;
    }
    setCurrentStep("npci");
  };

  const handlePreviousStep = () => {
    setCurrentStep("cbs");
  };

  const isUploading = uploadMutation.isPending;

  return (
    <div className="p-6 space-y-6">
      <div className="relative overflow-hidden rounded-3xl border bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-sky-100 via-white to-amber-50 px-6 py-8 shadow-sm">
        <div className="absolute -right-12 -top-12 h-40 w-40 rounded-full bg-sky-200/40 blur-2xl" />
        <div className="absolute -left-10 bottom-0 h-32 w-32 rounded-full bg-amber-200/50 blur-2xl" />
        <div className="relative z-10 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Reconciliation Console</p>
            <h1 className="mt-2 text-3xl font-bold text-foreground md:text-4xl">File Upload</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {currentStep === "cbs" && "Step 1 of 2: Upload CBS, GL and Switch files."}
              {currentStep === "npci" && "Step 2 of 2: Upload NPCI files (optional)."}
            </p>
          </div>
          <div className="flex items-center gap-3 rounded-full border bg-white/80 px-4 py-2 text-xs font-semibold text-slate-600 shadow-sm">
            <span className={`rounded-full px-3 py-1 ${currentStep === "cbs" ? "bg-slate-900 text-white" : "bg-slate-100"}`}>CBS / GL / Switch</span>
            <span className={`rounded-full px-3 py-1 ${currentStep === "npci" ? "bg-slate-900 text-white" : "bg-slate-100"}`}>NPCI</span>
          </div>
        </div>
      </div>

      <Tabs value={currentStep} onValueChange={setCurrentStep} className="w-full">
        <TabsList className="bg-muted/20 rounded-full p-1">
          <TabsTrigger
            value="cbs"
            className="rounded-full data-[state=active]:bg-slate-900 data-[state=active]:text-white"
          >
            CBS/ GL/ Switch
          </TabsTrigger>
          <TabsTrigger
            value="npci"
            className="rounded-full data-[state=active]:bg-slate-900 data-[state=active]:text-white"
          >
            NPCI Files
          </TabsTrigger>
        </TabsList>
       
        {/* CBS/GL File Tab */}
        <TabsContent value="cbs">
          <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]">
            <div className="space-y-6">
              <div className="rounded-2xl border bg-white p-4 text-sm text-muted-foreground shadow-sm">
                <p>Upload your CBS (Core Banking System) and GL (General Ledger) files for reconciliation.</p>
                <p className="mt-2">All required files must be selected to proceed.</p>
              </div>

              <Card className="shadow-lg">
                <CardContent className="space-y-8 pt-8">
                {/* CBS Inward File */}
                <div className="space-y-2">
                  <Label className="text-base font-semibold">
                    Upload CBS Inward File <span className="ml-2 rounded-full bg-rose-100 px-2 py-0.5 text-xs text-rose-700">Required</span>
                  </Label>
                  <div className="rounded-2xl border border-dashed bg-slate-50 p-4">
                    <div className="flex flex-wrap items-center gap-3">
                      <Button
                        variant="outline"
                        className="rounded-full px-6"
                        onClick={() => document.getElementById('cbs-inward')?.click()}
                        disabled={isUploading}
                      >
                        <Upload className="w-4 h-4 mr-2" />
                        Choose File
                      </Button>
                      <span className="text-xs text-muted-foreground">CSV, XLSX</span>
                    </div>
                    <input
                      id="cbs-inward"
                      type="file"
                      className="hidden"
                      accept=".csv,.xlsx"
                      onChange={handleFileChange(setCbsInward)}
                    />
                    {cbsInward && (
                      <div className="mt-3 flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-emerald-500" />
                        <span className="text-sm text-muted-foreground">{cbsInward.name}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* CBS Outward File */}
                <div className="space-y-2">
                  <Label className="text-base font-semibold">
                    Upload CBS Outward File <span className="ml-2 rounded-full bg-rose-100 px-2 py-0.5 text-xs text-rose-700">Required</span>
                  </Label>
                  <div className="rounded-2xl border border-dashed bg-slate-50 p-4">
                    <div className="flex flex-wrap items-center gap-3">
                      <Button
                        variant="outline"
                        className="rounded-full px-6"
                        onClick={() => document.getElementById('cbs-outward')?.click()}
                        disabled={isUploading}
                      >
                        <Upload className="w-4 h-4 mr-2" />
                        Choose File
                      </Button>
                      <span className="text-xs text-muted-foreground">CSV, XLSX</span>
                    </div>
                    <input
                      id="cbs-outward"
                      type="file"
                      className="hidden"
                      accept=".csv,.xlsx"
                      onChange={handleFileChange(setCbsOutward)}
                    />
                    {cbsOutward && (
                      <div className="mt-3 flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-emerald-500" />
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
                    className="max-w-md rounded-xl"
                  />
                </div>

                {/* Switch File (moved into CBS tab) */}
                <div className="space-y-2">
                  <Label className="text-base font-semibold">
                    Upload Switch File <span className="ml-2 rounded-full bg-rose-100 px-2 py-0.5 text-xs text-rose-700">Required</span>
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Assumption is that the Inward & Outward Transactions are provided in a single file
                  </p>
                  <div className="rounded-2xl border border-dashed bg-slate-50 p-4">
                    <div className="flex flex-wrap items-center gap-3">
                      <Button
                        variant="outline"
                        className="rounded-full px-6"
                        onClick={() => document.getElementById('switch-file')?.click()}
                        disabled={isUploading}
                      >
                        <Upload className="w-4 h-4 mr-2" />
                        Choose File
                      </Button>
                      <span className="text-xs text-muted-foreground">CSV, XLSX</span>
                    </div>
                    <input
                      id="switch-file"
                      type="file"
                      className="hidden"
                      accept=".csv,.xlsx"
                      onChange={handleFileChange(setSwitchFile)}
                    />
                    {switchFile && (
                      <div className="mt-3 flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-emerald-500" />
                        <span className="text-sm text-muted-foreground">{switchFile.name}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex justify-end pt-4">
                  <Button
                    className="rounded-full px-12 py-6 text-lg bg-slate-900 hover:bg-slate-800 shadow-lg hover:shadow-xl transition-all"
                    onClick={handleNextStep}
                    disabled={isUploading || !cbsInward || !cbsOutward || !switchFile}
                  >
                    Next
                  </Button>
                </div>
                </CardContent>
              </Card>
            </div>

            <div className="space-y-4">
              <div className="rounded-2xl border bg-white p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Required</p>
                <div className="mt-3 space-y-2 text-sm text-muted-foreground">
                  <p>CBS Inward</p>
                  <p>CBS Outward</p>
                  <p>Switch File</p>
                </div>
              </div>
              <div className="rounded-2xl border bg-slate-900 p-5 text-white shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-200">Tip</p>
                <p className="mt-2 text-sm text-slate-200">
                  Keep filenames consistent and ensure today's date is embedded for NPCI uploads.
                </p>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* NPCI Files Tab - Secondary / Fall-back Upload Mode */}
        <TabsContent value="npci">
          <div className="space-y-6 mt-6">
            <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4">
              <p className="text-sm text-amber-900">
                <strong>Secondary / Fall-back Upload Mode:</strong> Use this section to upload NPCI files as an alternative or backup method. NPCI files are optional and support multiple cycles (1-10).
              </p>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4 mb-6">
              <p className="text-sm text-blue-900">
                <strong>Note:</strong> NPCI files are optional. You can upload any combination of NPCI Inward, NPCI Outward, NTSL, and Adjustment files.
              </p>
            </div>
            <div className="flex justify-end mb-2">
              <Link to="/cycle-skip">
                <Button variant="ghost" className="rounded-full">Open NPCI Cycle</Button>
              </Link>
            </div>
            <Card className="shadow-lg">
              <CardContent className="space-y-8 pt-8">
                {/* NPCI Raw I/W File */}
                <div className="space-y-3">
                  <Label className="text-base font-semibold">NPCI Raw I/W File</Label>
                  <div className="text-sm text-muted-foreground mb-1">Cycle will be auto-detected from filename or file content.</div>
                  <div className="rounded-2xl border border-dashed bg-slate-50 p-4">
                    <Button
                      variant="outline"
                      className="rounded-full px-6"
                      onClick={() => document.getElementById('npci-inward')?.click()}
                      disabled={isUploading}
                    >
                      <Upload className="w-4 h-4 mr-2" />
                      Choose Files
                    </Button>
                    <span className="ml-3 text-xs text-muted-foreground">Multiple files supported</span>
                  </div>
                  <input
                    id="npci-inward"
                    type="file"
                    className="hidden"
                    accept=".csv,.xlsx"
                    multiple
                    onChange={handleNpciFileChange('npci_inward')}
                  />
                  {npciFiles.npci_inward?.length ? (
                    <div className="mt-2 space-y-1">
                      {npciFiles.npci_inward.map((file) => (
                        <div key={file.name} className="flex items-center gap-2">
                          <CheckCircle className="w-4 h-4 text-green-500" />
                          <span className="text-sm text-muted-foreground">{file.name}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>

                {/* NPCI Raw O/W File */}
                <div className="space-y-3">
                  <Label className="text-base font-semibold">NPCI Raw O/W File</Label>
                  <div className="text-sm text-muted-foreground mb-1">Cycle will be auto-detected from filename or file content.</div>
                  <div className="rounded-2xl border border-dashed bg-slate-50 p-4">
                    <Button
                      variant="outline"
                      className="rounded-full px-6"
                      onClick={() => document.getElementById('npci-outward')?.click()}
                      disabled={isUploading}
                    >
                      <Upload className="w-4 h-4 mr-2" />
                      Choose Files
                    </Button>
                    <span className="ml-3 text-xs text-muted-foreground">Multiple files supported</span>
                  </div>
                  <input
                    id="npci-outward"
                    type="file"
                    className="hidden"
                    accept=".csv,.xlsx"
                    multiple
                    onChange={handleNpciFileChange('npci_outward')}
                  />
                  {npciFiles.npci_outward?.length ? (
                    <div className="mt-2 space-y-1">
                      {npciFiles.npci_outward.map((file) => (
                        <div key={file.name} className="flex items-center gap-2">
                          <CheckCircle className="w-4 h-4 text-green-500" />
                          <span className="text-sm text-muted-foreground">{file.name}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>

                {/* NTSL File */}
                <div className="space-y-3">
                  <Label className="text-base font-semibold">NTSL File</Label>
                  <div className="text-sm text-muted-foreground mb-2">
                    Cycle for NTSL will be auto-detected from filename or file content.
                  </div>
                  <div className="rounded-2xl border border-dashed bg-slate-50 p-4">
                    <Button
                      variant="outline"
                      className="rounded-full px-6"
                      onClick={() => document.getElementById('ntsl-file')?.click()}
                      disabled={isUploading}
                    >
                      <Upload className="w-4 h-4 mr-2" />
                      Choose Files
                    </Button>
                    <span className="ml-3 text-xs text-muted-foreground">Multiple files supported</span>
                  </div>
                  <input
                    id="ntsl-file"
                    type="file"
                    className="hidden"
                    accept=".csv,.xlsx"
                    multiple
                    onChange={handleNpciFileChange('ntsl')}
                  />
                  {npciFiles.ntsl?.length ? (
                    <div className="mt-2 space-y-1">
                      {npciFiles.ntsl.map((file) => (
                        <div key={file.name} className="flex items-center gap-2">
                          <CheckCircle className="w-4 h-4 text-green-500" />
                          <span className="text-sm text-muted-foreground">{file.name}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>

                {/* Adjustment File */}
                <div className="space-y-3">
                  <Label className="text-base font-semibold">Adjustment File</Label>
                  <div className="rounded-2xl border border-dashed bg-slate-50 p-4">
                    <Button
                      variant="outline"
                      className="rounded-full px-6"
                      onClick={() => document.getElementById('adjustment-file')?.click()}
                      disabled={isUploading}
                    >
                      <Upload className="w-4 h-4 mr-2" />
                      Choose Files
                    </Button>
                    <span className="ml-3 text-xs text-muted-foreground">Multiple files supported</span>
                  </div>
                  <input
                    id="adjustment-file"
                    type="file"
                    className="hidden"
                    accept=".csv,.xlsx"
                    multiple
                    onChange={handleNpciFileChange('adjustment')}
                  />
                  {npciFiles.adjustment?.length ? (
                    <div className="mt-2 space-y-1">
                      {npciFiles.adjustment.map((file) => (
                        <div key={file.name} className="flex items-center gap-2">
                          <CheckCircle className="w-4 h-4 text-green-500" />
                          <span className="text-sm text-muted-foreground">{file.name}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}
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
                    className="rounded-full px-12 py-6 text-lg bg-slate-900 hover:bg-slate-800 shadow-lg hover:shadow-xl transition-all"
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
