import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Skeleton } from "../components/ui/skeleton";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../lib/api";
import { format } from "date-fns";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line
} from "recharts";
import {
  TrendingUp, TrendingDown, Download,
  DollarSign, AlertCircle
} from "lucide-react";
import { ChartContainer } from "../components/ui/chart";
import { toast } from "sonner";

// Chart colors
const COLORS = {
  income: "#10b981",
  expense: "#ef4444",
  net: "#3b82f6",
  primary: "#6366f1",
  secondary: "#8b5cf6",
  tertiary: "#ec4899",
  quaternary: "#f59e0b"
};

const EXPENSE_COLORS = ["#ef4444", "#f97316", "#f59e0b", "#eab308", "#84cc16"];

type IncomeExpenseDashboardProps = {
  dateFrom?: string;
  dateTo?: string;
};

export default function IncomeExpenseDashboard({ dateFrom, dateTo }: IncomeExpenseDashboardProps) {
  const formatDateForAPI = (date: string | undefined) => date || "";

  // Fetch income/expense data
  const { data: incomeExpenseData, isLoading, error } = useQuery({
    queryKey: ['income-expense', formatDateForAPI(dateFrom), formatDateForAPI(dateTo)],
    queryFn: async () => {
      if (!dateFrom || !dateTo) return null;
      return await apiClient.getIncomeExpenseData(
        formatDateForAPI(dateFrom),
        formatDateForAPI(dateTo)
      );
    },
    enabled: !!dateFrom && !!dateTo
  });

  // Download Excel handler
  const handleDownloadExcel = async () => {
    try {
      if (!dateFrom || !dateTo) {
        toast.error("Please select date range");
        return;
      }

      const response = await apiClient.downloadIncomeExpenseExcel(
        formatDateForAPI(dateFrom),
        formatDateForAPI(dateTo)
      );

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Income_Expense_MIS_Report_${formatDateForAPI(dateFrom)}_to_${formatDateForAPI(dateTo)}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      toast.success("Excel report downloaded successfully");
    } catch (error: any) {
      console.error("Download error:", error);
      toast.error("Failed to download Excel report");
    }
  };

  // Prepare chart data
  const prepareIncomeVsExpenseData = () => {
    if (!incomeExpenseData?.date_wise_data) return [];
    return incomeExpenseData.date_wise_data.map((item: any) => ({
      date: format(new Date(item.date), "MMM dd"),
      Income: item.income,
      Expense: item.expense
    }));
  };

  const prepareExpenseBreakdownData = () => {
    if (!incomeExpenseData?.expense_breakdown) return [];
    
    const { interchange_expense, npci_switching_fees, gst_expense } = incomeExpenseData.expense_breakdown;
    
    return [
      {
        name: "Interchange Expense",
        value: (
          interchange_expense.remitter_u2_fee +
          interchange_expense.remitter_u3_fee +
          interchange_expense.remitter_p2a_declined
        )
      },
      {
        name: "NPCI Switching Fees",
        value: (
          npci_switching_fees.remitter_u2_npci +
          npci_switching_fees.remitter_u3_npci
        )
      },
      {
        name: "GST Expense",
        value: (
          gst_expense.remitter_u2_fee_gst +
          gst_expense.remitter_u3_fee_gst +
          gst_expense.remitter_u2_npci_gst +
          gst_expense.remitter_u3_npci_gst
        )
      }
    ];
  };

  const prepareTrendData = () => {
    if (!incomeExpenseData?.date_wise_data) return [];
    return incomeExpenseData.date_wise_data.map((item: any) => ({
      date: format(new Date(item.date), "MMM dd"),
      Income: item.income,
      Expense: item.expense,
      Net: item.net
    }));
  };

  const summary = incomeExpenseData?.summary || { total_income: 0, total_expense: 0, net_position: 0 };
  const incomeBreakdown = incomeExpenseData?.income_breakdown;
  const expenseBreakdown = incomeExpenseData?.expense_breakdown;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Income & Expense Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">NTSL / NPCI Settlement Analysis</p>
        </div>
        <Button onClick={handleDownloadExcel} disabled={!dateFrom || !dateTo} className="gap-2">
          <Download className="w-4 h-4" />
          Download MIS Report
        </Button>
      </div>
      {!dateFrom || !dateTo ? (
        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="flex items-center gap-2 p-4">
            <AlertCircle className="w-5 h-5 text-blue-600" />
            <p className="text-blue-700">Select a date range from the Dashboard filter to view data.</p>
          </CardContent>
        </Card>
      ) : null}

      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      )}

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-2 p-4">
            <AlertCircle className="w-5 h-5 text-red-600" />
            <p className="text-red-600">Failed to load income/expense data</p>
          </CardContent>
        </Card>
      )}

      {!isLoading && !error && incomeExpenseData && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card className="border-green-200 bg-green-50">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-green-700">Total Income</CardTitle>
                <TrendingUp className="w-5 h-5 text-green-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-900">
                  ₹{summary.total_income.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </div>
                {incomeBreakdown && (
                  <div className="mt-4 space-y-1 text-xs text-green-700">
                    <div className="flex justify-between">
                      <span>U2 Payer PSP Fees:</span>
                      <span className="font-medium">₹{incomeBreakdown.interchange_income.u2_payer_psp_fees.toLocaleString('en-IN')}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>U3 Payer PSP Fees:</span>
                      <span className="font-medium">₹{incomeBreakdown.interchange_income.u3_payer_psp_fees.toLocaleString('en-IN')}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Beneficiary U3 Fee:</span>
                      <span className="font-medium">₹{incomeBreakdown.interchange_income.beneficiary_u3_fee.toLocaleString('en-IN')}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>GST Income:</span>
                      <span className="font-medium">₹{incomeBreakdown.gst_income.beneficiary_u3_fee_gst.toLocaleString('en-IN')}</span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="border-red-200 bg-red-50">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-red-700">Total Expense</CardTitle>
                <TrendingDown className="w-5 h-5 text-red-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-900">
                  ₹{summary.total_expense.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </div>
                {expenseBreakdown && (
                  <div className="mt-4 space-y-1 text-xs text-red-700">
                    <div className="flex justify-between">
                      <span>Interchange Expense:</span>
                      <span className="font-medium">
                        ₹{(expenseBreakdown.interchange_expense.remitter_u2_fee + 
                           expenseBreakdown.interchange_expense.remitter_u3_fee + 
                           expenseBreakdown.interchange_expense.remitter_p2a_declined).toLocaleString('en-IN')}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>NPCI Switching Fees:</span>
                      <span className="font-medium">
                        ₹{(expenseBreakdown.npci_switching_fees.remitter_u2_npci + 
                           expenseBreakdown.npci_switching_fees.remitter_u3_npci).toLocaleString('en-IN')}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>GST Expense:</span>
                      <span className="font-medium">
                        ₹{(expenseBreakdown.gst_expense.remitter_u2_fee_gst + 
                           expenseBreakdown.gst_expense.remitter_u3_fee_gst + 
                           expenseBreakdown.gst_expense.remitter_u2_npci_gst + 
                           expenseBreakdown.gst_expense.remitter_u3_npci_gst).toLocaleString('en-IN')}
                      </span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className={cn(
              "border-blue-200",
              summary.net_position >= 0 ? "bg-blue-50" : "bg-orange-50"
            )}>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-blue-700">Net Position</CardTitle>
                <DollarSign className="w-5 h-5 text-blue-600" />
              </CardHeader>
              <CardContent>
                <div className={cn(
                  "text-2xl font-bold",
                  summary.net_position >= 0 ? "text-blue-900" : "text-orange-900"
                )}>
                  ₹{summary.net_position.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </div>
                <p className="text-xs text-gray-600 mt-2">
                  {summary.net_position >= 0 ? "Positive Position" : "Negative Position"}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Income vs Expense Bar Chart */}
            <Card>
              <CardHeader>
                <CardTitle>Income vs Expense</CardTitle>
              </CardHeader>
              <CardContent>
                <ChartContainer config={{}} className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={prepareIncomeVsExpenseData()}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="Income" fill={COLORS.income} />
                      <Bar dataKey="Expense" fill={COLORS.expense} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartContainer>
              </CardContent>
            </Card>

            {/* Expense Breakdown Pie Chart */}
            <Card>
              <CardHeader>
                <CardTitle>Expense Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                <ChartContainer config={{}} className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={prepareExpenseBreakdownData()}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={(entry) => `${entry.name}: ₹${entry.value.toLocaleString('en-IN')}`}
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {prepareExpenseBreakdownData().map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={EXPENSE_COLORS[index % EXPENSE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </ChartContainer>
              </CardContent>
            </Card>
          </div>

          {/* Date-wise Trend Line Chart */}
          <Card>
            <CardHeader>
              <CardTitle>Date-wise Trend</CardTitle>
            </CardHeader>
            <CardContent>
              <ChartContainer config={{}} className="h-96">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={prepareTrendData()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="Income" stroke={COLORS.income} strokeWidth={2} />
                    <Line type="monotone" dataKey="Expense" stroke={COLORS.expense} strokeWidth={2} />
                    <Line type="monotone" dataKey="Net" stroke={COLORS.net} strokeWidth={2} strokeDasharray="5 5" />
                  </LineChart>
                </ResponsiveContainer>
              </ChartContainer>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
