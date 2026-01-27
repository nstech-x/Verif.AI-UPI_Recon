import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Slider } from "../components/ui/slider";
import { Separator } from "../components/ui/separator";
import { Save, RefreshCw, Settings, Info, CheckCircle2, X } from "lucide-react";
import { useToast } from "../hooks/use-toast";
import { apiClient } from "../lib/api";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "../components/ui/alert";

export default function AutoMatch() {
  const { toast } = useToast();
  const [enableAutoMatch, setEnableAutoMatch] = useState(true);
  const [amountTolerance, setAmountTolerance] = useState(0.0);
  const [dateToleranceDays, setDateToleranceDays] = useState(0);
  const [isSaving, setIsSaving] = useState(false);

  const handleSaveParameters = async () => {
    try {
      setIsSaving(true);
      
      await apiClient.setAutoMatchParameters({
        amount_tolerance: amountTolerance,
        date_tolerance_days: dateToleranceDays,
        enable_auto_match: enableAutoMatch
      });

      toast({
        title: "Success",
        description: "Auto-match parameters have been saved successfully",
      });
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to save parameters. Please try again.",
        variant: "destructive"
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setEnableAutoMatch(true);
    setAmountTolerance(0.0);
    setDateToleranceDays(0);
    
    toast({
      title: "Reset",
      description: "Parameters have been reset to defaults",
    });
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-foreground">Auto Match Parameters</h1>
        <p className="text-muted-foreground">Configure automatic transaction matching rules</p>
      </div>

      {/* Info Alert */}
      <Alert>
        <Info className="h-4 w-4" />
        <AlertTitle>About Auto Match</AlertTitle>
        <AlertDescription>
          Auto-match automatically reconciles transactions between CBS, Switch, and NPCI systems based on the parameters you set below.
          Transactions within the specified tolerances will be automatically matched during reconciliation.
        </AlertDescription>
      </Alert>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Configuration Panel */}
        <Card className="lg:col-span-2 shadow-lg">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="w-5 h-5" />
              Matching Parameters
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Enable/Disable Auto Match */}
            <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
              <div className="space-y-0.5">
                <Label htmlFor="enable-auto-match" className="text-base font-semibold">
                  Enable Auto Match
                </Label>
                <p className="text-sm text-muted-foreground">
                  Automatically match transactions during reconciliation
                </p>
              </div>
              <Switch
                id="enable-auto-match"
                checked={enableAutoMatch}
                onCheckedChange={setEnableAutoMatch}
              />
            </div>

            <Separator />

            {/* Amount Tolerance */}
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="amount-tolerance" className="text-base font-semibold">
                  Amount Tolerance (₹)
                </Label>
                <p className="text-sm text-muted-foreground">
                  Maximum allowed difference in transaction amounts for auto-matching
                </p>
              </div>
              
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <Slider
                    id="amount-tolerance"
                    value={[amountTolerance]}
                    onValueChange={(value) => setAmountTolerance(value[0])}
                    max={100}
                    step={0.5}
                    className="flex-1"
                    disabled={!enableAutoMatch}
                  />
                  <div className="w-24">
                    <Input
                      type="number"
                      value={amountTolerance}
                      onChange={(e) => setAmountTolerance(parseFloat(e.target.value) || 0)}
                      step="0.5"
                      min="0"
                      max="100"
                      disabled={!enableAutoMatch}
                      className="text-right"
                    />
                  </div>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>₹0 (Exact match)</span>
                  <span>Current: ₹{amountTolerance.toFixed(2)}</span>
                  <span>₹100 (Maximum)</span>
                </div>
              </div>
            </div>

            <Separator />

            {/* Date Tolerance */}
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="date-tolerance" className="text-base font-semibold">
                  Date Tolerance (Days)
                </Label>
                <p className="text-sm text-muted-foreground">
                  Maximum allowed difference in transaction dates for auto-matching
                </p>
              </div>
              
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <Slider
                    id="date-tolerance"
                    value={[dateToleranceDays]}
                    onValueChange={(value) => setDateToleranceDays(value[0])}
                    max={7}
                    step={1}
                    className="flex-1"
                    disabled={!enableAutoMatch}
                  />
                  <div className="w-24">
                    <Input
                      type="number"
                      value={dateToleranceDays}
                      onChange={(e) => setDateToleranceDays(parseInt(e.target.value) || 0)}
                      step="1"
                      min="0"
                      max="7"
                      disabled={!enableAutoMatch}
                      className="text-right"
                    />
                  </div>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>0 days (Same day)</span>
                  <span>Current: {dateToleranceDays} day{dateToleranceDays !== 1 ? 's' : ''}</span>
                  <span>7 days (Maximum)</span>
                </div>
              </div>
            </div>

            <Separator />

            {/* Action Buttons */}
            <div className="flex gap-3 pt-4">
              <Button 
                onClick={handleSaveParameters}
                disabled={isSaving || !enableAutoMatch}
                className="flex-1 bg-brand-blue hover:bg-brand-mid"
              >
                {isSaving ? (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4 mr-2" />
                    Save Parameters
                  </>
                )}
              </Button>
              <Button 
                variant="outline" 
                onClick={handleReset}
                disabled={isSaving}
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Reset to Defaults
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Preview Panel */}
        <Card className="shadow-lg">
          <CardHeader>
            <CardTitle>Current Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3">
              <div className="flex justify-between items-center p-3 bg-muted/30 rounded-lg">
                <span className="text-sm font-medium">Status</span>
                <span className={`text-sm font-semibold ${enableAutoMatch ? 'text-green-600' : 'text-red-600'}`}>
                  {enableAutoMatch ? 'Enabled' : 'Disabled'}
                </span>
              </div>

              <div className="flex justify-between items-center p-3 bg-muted/30 rounded-lg">
                <span className="text-sm font-medium">Amount Tolerance</span>
                <span className="text-sm font-semibold text-brand-blue">
                  ±₹{amountTolerance.toFixed(2)}
                </span>
              </div>

              <div className="flex justify-between items-center p-3 bg-muted/30 rounded-lg">
                <span className="text-sm font-medium">Date Tolerance</span>
                <span className="text-sm font-semibold text-brand-blue">
                  ±{dateToleranceDays} day{dateToleranceDays !== 1 ? 's' : ''}
                </span>
              </div>
            </div>

            <Separator />

            <div className="space-y-2">
              <h4 className="text-sm font-semibold">Matching Rules</h4>
              <div className="text-xs text-muted-foreground space-y-2">
                <p className="flex items-center gap-1"><CheckCircle2 className="h-3 w-3 text-green-600" /> RRN must match exactly</p>
                <p className="flex items-center gap-1"><CheckCircle2 className="h-3 w-3 text-green-600" /> Amount difference ≤ ₹{amountTolerance.toFixed(2)}</p>
                <p className="flex items-center gap-1"><CheckCircle2 className="h-3 w-3 text-green-600" /> Date difference ≤ {dateToleranceDays} day{dateToleranceDays !== 1 ? 's' : ''}</p>
                <p className="flex items-center gap-1"><CheckCircle2 className="h-3 w-3 text-green-600" /> All three systems must have the transaction</p>
              </div>
            </div>

            <Separator />

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <p className="text-xs text-blue-800">
                <strong>Note:</strong> These parameters will be applied during the next reconciliation run.
                Existing reconciliation results will not be affected.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Examples Section */}
      <Card className="shadow-lg">
        <CardHeader>
          <CardTitle>Example Scenarios</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 border rounded-lg space-y-2">
              <h4 className="font-semibold text-sm">Exact Match</h4>
              <div className="text-xs text-muted-foreground space-y-1">
                <p>CBS: ₹1000.00, 2024-01-15</p>
                <p>Switch: ₹1000.00, 2024-01-15</p>
                <p>NPCI: ₹1000.00, 2024-01-15</p>
              </div>
              <div className="text-xs font-semibold text-green-600 flex items-center gap-1">
                <CheckCircle2 className="h-4 w-4" /> Will Match
              </div>
            </div>

            <div className="p-4 border rounded-lg space-y-2">
              <h4 className="font-semibold text-sm">Within Tolerance</h4>
              <div className="text-xs text-muted-foreground space-y-1">
                <p>CBS: ₹1000.00, 2024-01-15</p>
                <p>Switch: ₹1000.50, 2024-01-15</p>
                <p>NPCI: ₹1000.00, 2024-01-16</p>
              </div>
              <div className={`text-xs font-semibold flex items-center gap-1 ${amountTolerance >= 0.5 && dateToleranceDays >= 1 ? 'text-green-600' : 'text-red-600'}`}>
                {amountTolerance >= 0.5 && dateToleranceDays >= 1 ? (
                  <><CheckCircle2 className="h-4 w-4" /> Will Match</>
                ) : (
                  <><X className="h-4 w-4" /> Will Not Match</>
                )}
              </div>
            </div>

            <div className="p-4 border rounded-lg space-y-2">
              <h4 className="font-semibold text-sm">Outside Tolerance</h4>
              <div className="text-xs text-muted-foreground space-y-1">
                <p>CBS: ₹1000.00, 2024-01-15</p>
                <p>Switch: ₹1100.00, 2024-01-15</p>
                <p>NPCI: ₹1000.00, 2024-01-20</p>
              </div>
              <div className="text-xs font-semibold text-red-600">✗ Will Not Match</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}