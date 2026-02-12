import { useState } from "react";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Loader2, CheckCircle } from "lucide-react";
import { useToast } from "../hooks/use-toast";
import { useMutation } from "@tanstack/react-query";
import { apiClient } from "../lib/api";
import { useDemoData } from "../contexts/DemoDataContext";
import { useNavigate } from "react-router-dom";

export default function FileUpload() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { setDemoMode } = useDemoData();
  const [date] = useState(new Date().toISOString().split('T')[0]);
  const [cbsInward, setCbsInward] = useState<File | null>(null);
  const [cbsOutward, setCbsOutward] = useState<File | null>(null);
  const [cbsBalance, setCbsBalance] = useState("");
  const [switchFile, setSwitchFile] = useState<File | null>(null);
  const [npciFiles, setNpciFiles] = useState<Record<string, File[]>>({});
  const [ntslFiles, setNtslFiles] = useState<File[]>([]);
  const [adjustmentFiles, setAdjustmentFiles] = useState<File[]>([]);
  const [drcFiles, setDrcFiles] = useState<File[]>([]);

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
        cbs_balance: cbsBalance,
        transaction_date: date,
      };

      const npciInward = [
        ...(npciFiles.npci_inward_p2p || []),
        ...(npciFiles.npci_inward_p2m || []),
      ];
      const npciOutward = [
        ...(npciFiles.npci_outward_p2p || []),
        ...(npciFiles.npci_outward_p2m || []),
      ];
      if (npciInward.length) uploadData.npci_inward = npciInward;
      if (npciOutward.length) uploadData.npci_outward = npciOutward;
      if (ntslFiles.length) uploadData.ntsl = ntslFiles;
      if (adjustmentFiles.length) uploadData.adjustment = adjustmentFiles;
      if (drcFiles.length) uploadData.drc = drcFiles;

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

      // Ensure real-time data is shown after upload
      setDemoMode(false);

      toast({
        title: "Files uploaded successfully",
        description: `Run ID: ${data.run_id}. Uploaded: ${fileNames}.`,
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
      setNtslFiles([]);
      setAdjustmentFiles([]);
      setDrcFiles([]);
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
      const name = (file.name || "").toUpperCase();
      const npciMatch = name.match(/^(ISSR|ACQR)(P2P|P2M)[A-Z0-9]{4}(\d{6})_(\d{1,2})C\./);

      if (!npciMatch) {
        toast({
          title: "Invalid filename",
          description: "NPCI filename must follow ISSR/ACQR + P2P/P2M + BANK + DDMMYY + _<cycle>C.",
          variant: "destructive",
        });
        return false;
      }

      const direction = npciMatch[1];
      const txnType = npciMatch[2];

      if (fileType.includes('inward') && direction !== 'ISSR') {
        toast({
          title: "Invalid file direction",
          description: "NPCI inward files must start with ISSR.",
          variant: "destructive",
        });
        return false;
      }
      if (fileType.includes('outward') && direction !== 'ACQR') {
        toast({
          title: "Invalid file direction",
          description: "NPCI outward files must start with ACQR.",
          variant: "destructive",
        });
        return false;
      }
      if (fileType.includes('p2p') && txnType !== 'P2P') {
        toast({
          title: "Invalid transaction type",
          description: "NPCI P2P files must include P2P.",
          variant: "destructive",
        });
        return false;
      }
      if (fileType.includes('p2m') && txnType !== 'P2M') {
        toast({
          title: "Invalid transaction type",
          description: "NPCI P2M files must include P2M.",
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
    setNpciFiles((prev) => ({
      ...prev,
      [fileType]: accepted,
    }));
  };

  const handleAuxFileChange = (
    setter: (files: File[]) => void,
    pattern: RegExp,
    errorDescription: string
  ) => (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const files = Array.from(e.target.files);
    const accepted = files.filter((file) => pattern.test((file.name || "").toUpperCase()));
    if (accepted.length !== files.length) {
      toast({
        title: "Invalid filename",
        description: errorDescription,
        variant: "destructive",
      });
    }
    if (accepted.length > 0) setter(accepted);
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
              Upload CBS, Switch, NPCI, NTSL, Adjustment, and DRC files for reconciliation.
            </p>
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <div className="rounded-2xl border bg-white p-4 text-sm text-muted-foreground shadow-sm">
            <p>Upload all reconciliation inputs from a single page. CBS Inward, CBS Outward, and Switch are required.</p>
          </div>

          <Card className="shadow-lg">
            <CardContent className="pt-6">
              <div className="overflow-hidden rounded-2xl border">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-3">File Name</th>
                      <th className="px-4 py-3">Browse</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    <tr>
                      <td className="px-4 py-3 font-medium">CBS (Inward)</td>
                      <td className="px-4 py-3">
                        <Button variant="link" className="px-0" onClick={() => document.getElementById('cbs-inward')?.click()} disabled={isUploading}>
                          Browse
                        </Button>
                        {cbsInward && (
                          <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                            <CheckCircle className="h-3 w-3 text-emerald-500" />
                            {cbsInward.name}
                          </div>
                        )}
                        <input id="cbs-inward" type="file" className="hidden" accept=".csv,.xlsx" onChange={handleFileChange(setCbsInward)} />
                      </td>
                    </tr>
                    <tr>
                      <td className="px-4 py-3 font-medium">CBS (Outward)</td>
                      <td className="px-4 py-3">
                        <Button variant="link" className="px-0" onClick={() => document.getElementById('cbs-outward')?.click()} disabled={isUploading}>
                          Browse
                        </Button>
                        {cbsOutward && (
                          <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                            <CheckCircle className="h-3 w-3 text-emerald-500" />
                            {cbsOutward.name}
                          </div>
                        )}
                        <input id="cbs-outward" type="file" className="hidden" accept=".csv,.xlsx" onChange={handleFileChange(setCbsOutward)} />
                      </td>
                    </tr>
                    <tr>
                      <td className="px-4 py-3 font-medium">Switch</td>
                      <td className="px-4 py-3">
                        <Button variant="link" className="px-0" onClick={() => document.getElementById('switch-file')?.click()} disabled={isUploading}>
                          Browse
                        </Button>
                        {switchFile && (
                          <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                            <CheckCircle className="h-3 w-3 text-emerald-500" />
                            {switchFile.name}
                          </div>
                        )}
                        <input id="switch-file" type="file" className="hidden" accept=".csv,.xlsx" onChange={handleFileChange(setSwitchFile)} />
                      </td>
                    </tr>
                    <tr>
                      <td className="px-4 py-3 font-medium">NPCI Raw Inward (P2P)</td>
                      <td className="px-4 py-3">
                        <Button variant="link" className="px-0" onClick={() => document.getElementById('npci-inward-p2p')?.click()} disabled={isUploading}>
                          Browse
                        </Button>
                        {npciFiles.npci_inward_p2p?.length ? (
                          <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                            {npciFiles.npci_inward_p2p.map((file) => (
                              <div key={file.name} className="flex items-center gap-2">
                                <CheckCircle className="h-3 w-3 text-emerald-500" />
                                {file.name}
                              </div>
                            ))}
                          </div>
                        ) : null}
                        <input id="npci-inward-p2p" type="file" className="hidden" accept=".csv,.xlsx" multiple onChange={handleNpciFileChange('npci_inward_p2p')} />
                      </td>
                    </tr>
                    <tr>
                      <td className="px-4 py-3 font-medium">NPCI Raw Outward (P2P)</td>
                      <td className="px-4 py-3">
                        <Button variant="link" className="px-0" onClick={() => document.getElementById('npci-outward-p2p')?.click()} disabled={isUploading}>
                          Browse
                        </Button>
                        {npciFiles.npci_outward_p2p?.length ? (
                          <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                            {npciFiles.npci_outward_p2p.map((file) => (
                              <div key={file.name} className="flex items-center gap-2">
                                <CheckCircle className="h-3 w-3 text-emerald-500" />
                                {file.name}
                              </div>
                            ))}
                          </div>
                        ) : null}
                        <input id="npci-outward-p2p" type="file" className="hidden" accept=".csv,.xlsx" multiple onChange={handleNpciFileChange('npci_outward_p2p')} />
                      </td>
                    </tr>
                    <tr>
                      <td className="px-4 py-3 font-medium">NPCI Raw Inward (P2M)</td>
                      <td className="px-4 py-3">
                        <Button variant="link" className="px-0" onClick={() => document.getElementById('npci-inward-p2m')?.click()} disabled={isUploading}>
                          Browse
                        </Button>
                        {npciFiles.npci_inward_p2m?.length ? (
                          <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                            {npciFiles.npci_inward_p2m.map((file) => (
                              <div key={file.name} className="flex items-center gap-2">
                                <CheckCircle className="h-3 w-3 text-emerald-500" />
                                {file.name}
                              </div>
                            ))}
                          </div>
                        ) : null}
                        <input id="npci-inward-p2m" type="file" className="hidden" accept=".csv,.xlsx" multiple onChange={handleNpciFileChange('npci_inward_p2m')} />
                      </td>
                    </tr>
                    <tr>
                      <td className="px-4 py-3 font-medium">NPCI Raw Outward (P2M)</td>
                      <td className="px-4 py-3">
                        <Button variant="link" className="px-0" onClick={() => document.getElementById('npci-outward-p2m')?.click()} disabled={isUploading}>
                          Browse
                        </Button>
                        {npciFiles.npci_outward_p2m?.length ? (
                          <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                            {npciFiles.npci_outward_p2m.map((file) => (
                              <div key={file.name} className="flex items-center gap-2">
                                <CheckCircle className="h-3 w-3 text-emerald-500" />
                                {file.name}
                              </div>
                            ))}
                          </div>
                        ) : null}
                        <input id="npci-outward-p2m" type="file" className="hidden" accept=".csv,.xlsx" multiple onChange={handleNpciFileChange('npci_outward_p2m')} />
                      </td>
                    </tr>
                    <tr>
                      <td className="px-4 py-3 font-medium">NTSL</td>
                      <td className="px-4 py-3">
                        <Button variant="link" className="px-0" onClick={() => document.getElementById('ntsl-file')?.click()} disabled={isUploading}>
                          Browse
                        </Button>
                        {ntslFiles.length ? (
                          <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                            {ntslFiles.map((file) => (
                              <div key={file.name} className="flex items-center gap-2">
                                <CheckCircle className="h-3 w-3 text-emerald-500" />
                                {file.name}
                              </div>
                            ))}
                          </div>
                        ) : null}
                        <input
                          id="ntsl-file"
                          type="file"
                          className="hidden"
                          accept=".csv,.xlsx"
                          multiple
                          onChange={handleAuxFileChange(
                            setNtslFiles,
                            /^UPINTSLP[A-Z0-9]{4}(\d{8})(?:_(\d{1,2})C)?\./,
                            "NTSL filename must follow UPINTSLP + BANK + DDMMYYYY (_<cycle>C optional)."
                          )}
                        />
                      </td>
                    </tr>
                    <tr>
                      <td className="px-4 py-3 font-medium">Adjustment File</td>
                      <td className="px-4 py-3">
                        <Button variant="link" className="px-0" onClick={() => document.getElementById('adjustment-file')?.click()} disabled={isUploading}>
                          Browse
                        </Button>
                        {adjustmentFiles.length ? (
                          <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                            {adjustmentFiles.map((file) => (
                              <div key={file.name} className="flex items-center gap-2">
                                <CheckCircle className="h-3 w-3 text-emerald-500" />
                                {file.name}
                              </div>
                            ))}
                          </div>
                        ) : null}
                        <input
                          id="adjustment-file"
                          type="file"
                          className="hidden"
                          accept=".csv,.xlsx"
                          multiple
                          onChange={handleAuxFileChange(
                            setAdjustmentFiles,
                            /^UPIADJREPORTP[A-Z0-9]{4}(\d{6})\./,
                            "Adjustment filename must follow UPIADJReportP + BANK + DDMMYY."
                          )}
                        />
                      </td>
                    </tr>
                    <tr>
                      <td className="px-4 py-3 font-medium">DRC</td>
                      <td className="px-4 py-3">
                        <Button variant="link" className="px-0" onClick={() => document.getElementById('drc-file')?.click()} disabled={isUploading}>
                          Browse
                        </Button>
                        {drcFiles.length ? (
                          <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                            {drcFiles.map((file) => (
                              <div key={file.name} className="flex items-center gap-2">
                                <CheckCircle className="h-3 w-3 text-emerald-500" />
                                {file.name}
                              </div>
                            ))}
                          </div>
                        ) : null}
                        <input
                          id="drc-file"
                          type="file"
                          className="hidden"
                          accept=".csv,.xlsx"
                          multiple
                          onChange={handleAuxFileChange(
                            setDrcFiles,
                            /^DRCREPORT[A-Z0-9]{4}(\d{6})\./,
                            "DRC filename must follow DRCReport + BANK + DDMMYY."
                          )}
                        />
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="mt-6 space-y-4">
                <div>
                  <Label className="text-base font-semibold">Enter CBS Closing Balance</Label>
                  <Input
                    type="text"
                    value={cbsBalance}
                    onChange={(e) => setCbsBalance(e.target.value)}
                    placeholder="Enter closing balance"
                    className="mt-2 max-w-md rounded-xl"
                  />
                </div>
                <div className="flex justify-end">
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
              </div>
            </CardContent>
          </Card>

          <Card className="shadow-sm">
            <CardContent className="pt-6">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-sm font-semibold">NPCI Cycle Skip</p>
                  <p className="text-xs text-muted-foreground">
                    Submit NPCI cycle skip requests with 1C–10C format.
                  </p>
                </div>
                <Button
                  variant="outline"
                  onClick={() => (window.location.href = "/cycle-skip")}
                >
                  Open NPCI Cycle Skip
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
              NPCI filenames must include ISSR/ACQR, P2P/P2M, bank code, date, and cycle. NTSL cycle is optional.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
