import { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface AuditEntry {
  audit_id: string;
  action: string;
  run_id: string;
  user_id: string;
  timestamp: string;
  level: string;
  details: Record<string, any>;
  source_system: string;
  ip_address: string;
}

interface AuditSummary {
  total_entries: number;
  by_action: Record<string, number>;
  by_level: Record<string, number>;
  by_user: Record<string, number>;
  critical_count: number;
  error_count: number;
  warning_count: number;
  date_range: {
    start: string;
    end: string;
  };
}

interface ComplianceReport {
  run_id: string;
  report_type: string;
  generated_at: string;
  entries: AuditEntry[];
  summary: AuditSummary;
  status: string;
}

const AUDIT_ACTIONS = [
  'FILE_UPLOADED',
  'FILE_VALIDATED',
  'RECON_STARTED',
  'RECON_COMPLETED',
  'RECON_FAILED',
  'CYCLE_PROCESSED',
  'TRANSACTION_MATCHED',
  'TRANSACTION_UNMATCHED',
  'ROLLBACK_INITIATED',
  'ROLLBACK_COMPLETED',
  'ROLLBACK_FAILED',
  'FORCE_MATCH_INITIATED',
  'FORCE_MATCH_COMPLETED',
  'EXCEPTION_LOGGED',
  'EXCEPTION_RESOLVED',
  'GL_PROOFING_CREATED',
  'VARIANCE_BRIDGE_ADDED',
  'VARIANCE_BRIDGE_RESOLVED',
  'DATA_EXPORTED',
  'DATA_DELETED',
];

const AUDIT_LEVELS = ['INFO', 'WARNING', 'ERROR', 'CRITICAL'];

const getLevelColor = (level: string) => {
  switch (level) {
    case 'CRITICAL':
      return 'bg-red-100 text-red-800 border-red-300';
    case 'ERROR':
      return 'bg-orange-100 text-orange-800 border-orange-300';
    case 'WARNING':
      return 'bg-yellow-100 text-yellow-800 border-yellow-300';
    case 'INFO':
      return 'bg-blue-100 text-blue-800 border-blue-300';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-300';
  }
};

export default function Audit() {
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [summary, setSummary] = useState<AuditSummary | null>(null);
  const [complianceReport, setComplianceReport] = useState<ComplianceReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filter states
  const [selectedRunId, setSelectedRunId] = useState('');
  const [selectedUserId, setSelectedUserId] = useState('');
  const [selectedAction, setSelectedAction] = useState('');
  const [selectedLevel, setSelectedLevel] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [reportType, setReportType] = useState('full');

  // Load audit summary
  const loadAuditSummary = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.getAuditSummary(selectedRunId || undefined);
      setSummary(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load audit summary');
    } finally {
      setLoading(false);
    }
  };

  // Load audit trail
  const loadAuditTrail = async () => {
    if (!selectedRunId) {
      setError('Please select a run ID');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.getAuditTrail(selectedRunId);
      let filtered = data;

      // Apply filters
      if (selectedAction) {
        filtered = filtered.filter((e: AuditEntry) => e.action === selectedAction);
      }
      if (selectedLevel) {
        filtered = filtered.filter((e: AuditEntry) => e.level === selectedLevel);
      }
      if (selectedUserId) {
        filtered = filtered.filter((e: AuditEntry) => e.user_id?.includes(selectedUserId));
      }

      setAuditEntries(filtered);
    } catch (err: any) {
      setError(err.message || 'Failed to load audit trail');
    } finally {
      setLoading(false);
    }
  };

  // Load audit by date range
  const loadByDateRange = async () => {
    if (!startDate || !endDate) {
      setError('Please select both start and end dates');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.getActionsByDateRange(startDate, endDate);
      let filtered = data;

      if (selectedAction) {
        filtered = filtered.filter((e: AuditEntry) => e.action === selectedAction);
      }
      if (selectedLevel) {
        filtered = filtered.filter((e: AuditEntry) => e.level === selectedLevel);
      }

      setAuditEntries(filtered);
    } catch (err: any) {
      setError(err.message || 'Failed to load audit entries');
    } finally {
      setLoading(false);
    }
  };

  // Load compliance report
  const loadComplianceReport = async () => {
    if (!selectedRunId) {
      setError('Please select a run ID for compliance report');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.generateComplianceReport(selectedRunId, reportType);
      setComplianceReport(data);
    } catch (err: any) {
      setError(err.message || 'Failed to generate compliance report');
    } finally {
      setLoading(false);
    }
  };

  // Export audit trail
  const exportAuditTrail = () => {
    if (auditEntries.length === 0) {
      setError('No audit entries to export');
      return;
    }

    const dataStr = JSON.stringify(auditEntries, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `audit_trail_${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    loadAuditSummary();
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-slate-900 mb-2">Audit & Compliance</h1>
          <p className="text-slate-600">
            Monitor all system operations, user activities, and generate compliance reports
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert className="mb-6 border-red-300 bg-red-50">
            <AlertDescription className="text-red-800">{error}</AlertDescription>
          </Alert>
        )}

        {/* Tabs */}
        <Tabs defaultValue="summary" className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-6">
            <TabsTrigger value="summary">Summary</TabsTrigger>
            <TabsTrigger value="trail">Audit Trail</TabsTrigger>
            <TabsTrigger value="compliance">Compliance Report</TabsTrigger>
          </TabsList>

          {/* Summary Tab */}
          <TabsContent value="summary" className="space-y-6">
            <Card className="border-slate-200 bg-white">
              <CardHeader>
                <CardTitle>Audit Summary</CardTitle>
                <CardDescription>Overview of all audit activities</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Summary Filters */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-slate-700 mb-2 block">
                      Run ID (Optional)
                    </label>
                    <Input
                      placeholder="Filter by run ID"
                      value={selectedRunId}
                      onChange={(e) => setSelectedRunId(e.target.value)}
                    />
                  </div>
                  <div className="flex items-end">
                    <Button onClick={loadAuditSummary} disabled={loading} className="w-full">
                      {loading ? 'Loading...' : 'Refresh Summary'}
                    </Button>
                  </div>
                </div>

                {/* Summary Stats */}
                {summary && (
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
                      <CardContent className="pt-6">
                        <div className="text-3xl font-bold text-blue-900">{summary.total_entries}</div>
                        <div className="text-sm text-blue-700 mt-1">Total Entries</div>
                      </CardContent>
                    </Card>

                    <Card className="bg-gradient-to-br from-red-50 to-red-100 border-red-200">
                      <CardContent className="pt-6">
                        <div className="text-3xl font-bold text-red-900">{summary.critical_count}</div>
                        <div className="text-sm text-red-700 mt-1">Critical Events</div>
                      </CardContent>
                    </Card>

                    <Card className="bg-gradient-to-br from-orange-50 to-orange-100 border-orange-200">
                      <CardContent className="pt-6">
                        <div className="text-3xl font-bold text-orange-900">{summary.error_count}</div>
                        <div className="text-sm text-orange-700 mt-1">Errors</div>
                      </CardContent>
                    </Card>

                    <Card className="bg-gradient-to-br from-yellow-50 to-yellow-100 border-yellow-200">
                      <CardContent className="pt-6">
                        <div className="text-3xl font-bold text-yellow-900">{summary.warning_count}</div>
                        <div className="text-sm text-yellow-700 mt-1">Warnings</div>
                      </CardContent>
                    </Card>
                  </div>
                )}

                {/* Distribution Charts */}
                {summary && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* By Level */}
                    <Card className="border-slate-200">
                      <CardHeader>
                        <CardTitle className="text-lg">By Level</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        {Object.entries(summary.by_level).map(([level, count]) => (
                          <div key={level} className="flex justify-between items-center">
                            <Badge className={`${getLevelColor(level)}`}>{level}</Badge>
                            <span className="text-sm font-semibold text-slate-700">{count}</span>
                          </div>
                        ))}
                      </CardContent>
                    </Card>

                    {/* By User */}
                    <Card className="border-slate-200">
                      <CardHeader>
                        <CardTitle className="text-lg">By User</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        {Object.entries(summary.by_user)
                          .sort(([, a], [, b]) => b - a)
                          .slice(0, 5)
                          .map(([user, count]) => (
                            <div key={user} className="flex justify-between items-center">
                              <span className="text-sm text-slate-700 truncate">{user}</span>
                              <Badge variant="outline">{count}</Badge>
                            </div>
                          ))}
                      </CardContent>
                    </Card>

                    {/* Top Actions */}
                    <Card className="border-slate-200">
                      <CardHeader>
                        <CardTitle className="text-lg">Top Actions</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        {Object.entries(summary.by_action)
                          .sort(([, a], [, b]) => b - a)
                          .slice(0, 5)
                          .map(([action, count]) => (
                            <div key={action} className="flex justify-between items-center">
                              <span className="text-sm text-slate-700 truncate">{action}</span>
                              <Badge variant="secondary">{count}</Badge>
                            </div>
                          ))}
                      </CardContent>
                    </Card>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Audit Trail Tab */}
          <TabsContent value="trail" className="space-y-6">
            <Card className="border-slate-200 bg-white">
              <CardHeader>
                <CardTitle>Audit Trail</CardTitle>
                <CardDescription>View detailed audit entries with filtering options</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Filters */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="text-sm font-medium text-slate-700 mb-2 block">Run ID</label>
                    <Input
                      placeholder="Enter run ID"
                      value={selectedRunId}
                      onChange={(e) => setSelectedRunId(e.target.value)}
                    />
                  </div>

                  <div>
                    <label className="text-sm font-medium text-slate-700 mb-2 block">Action</label>
                    <Select value={selectedAction} onValueChange={setSelectedAction}>
                      <SelectTrigger>
                        <SelectValue placeholder="All actions" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="">All actions</SelectItem>
                        {AUDIT_ACTIONS.map((action) => (
                          <SelectItem key={action} value={action}>
                            {action}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <label className="text-sm font-medium text-slate-700 mb-2 block">Level</label>
                    <Select value={selectedLevel} onValueChange={setSelectedLevel}>
                      <SelectTrigger>
                        <SelectValue placeholder="All levels" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="">All levels</SelectItem>
                        {AUDIT_LEVELS.map((level) => (
                          <SelectItem key={level} value={level}>
                            {level}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <label className="text-sm font-medium text-slate-700 mb-2 block">User ID</label>
                    <Input
                      placeholder="Filter by user"
                      value={selectedUserId}
                      onChange={(e) => setSelectedUserId(e.target.value)}
                    />
                  </div>

                  <div className="flex items-end gap-2">
                    <Button
                      onClick={loadAuditTrail}
                      disabled={loading || !selectedRunId}
                      className="flex-1"
                    >
                      {loading ? 'Loading...' : 'Load Trail'}
                    </Button>
                    <Button
                      onClick={exportAuditTrail}
                      disabled={auditEntries.length === 0}
                      variant="outline"
                      className="flex-1"
                    >
                      Export JSON
                    </Button>
                  </div>
                </div>

                {/* Entries Table */}
                {auditEntries.length > 0 && (
                  <div className="border border-slate-200 rounded-lg overflow-hidden">
                    <Table>
                      <TableHeader className="bg-slate-50">
                        <TableRow>
                          <TableHead className="text-xs font-semibold">Timestamp</TableHead>
                          <TableHead className="text-xs font-semibold">Action</TableHead>
                          <TableHead className="text-xs font-semibold">Level</TableHead>
                          <TableHead className="text-xs font-semibold">User</TableHead>
                          <TableHead className="text-xs font-semibold">Details</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {auditEntries.map((entry) => (
                          <TableRow key={entry.audit_id} className="hover:bg-slate-50">
                            <TableCell className="text-xs text-slate-600">
                              {format(new Date(entry.timestamp), 'MMM dd, HH:mm:ss')}
                            </TableCell>
                            <TableCell className="text-xs font-medium text-slate-900">
                              {entry.action}
                            </TableCell>
                            <TableCell className="text-xs">
                              <Badge className={getLevelColor(entry.level)}>{entry.level}</Badge>
                            </TableCell>
                            <TableCell className="text-xs text-slate-600">{entry.user_id || '-'}</TableCell>
                            <TableCell className="text-xs text-slate-600">
                              <div className="max-w-xs truncate">
                                {typeof entry.details === 'object'
                                  ? JSON.stringify(entry.details).slice(0, 50)
                                  : String(entry.details).slice(0, 50)}
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}

                {auditEntries.length === 0 && !loading && (
                  <div className="text-center py-8 text-slate-500">
                    {selectedRunId
                      ? 'No audit entries found for the selected filters'
                      : 'Select a run ID and click "Load Trail" to view audit entries'}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Compliance Report Tab */}
          <TabsContent value="compliance" className="space-y-6">
            <Card className="border-slate-200 bg-white">
              <CardHeader>
                <CardTitle>Compliance Report</CardTitle>
                <CardDescription>Generate compliance reports for audit requirements</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Report Filters */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="text-sm font-medium text-slate-700 mb-2 block">Run ID</label>
                    <Input
                      placeholder="Enter run ID"
                      value={selectedRunId}
                      onChange={(e) => setSelectedRunId(e.target.value)}
                    />
                  </div>

                  <div>
                    <label className="text-sm font-medium text-slate-700 mb-2 block">Report Type</label>
                    <Select value={reportType} onValueChange={setReportType}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select report type" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="full">Full Audit</SelectItem>
                        <SelectItem value="critical">Critical Events Only</SelectItem>
                        <SelectItem value="high_privilege">High Privilege Actions</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="flex items-end">
                    <Button
                      onClick={loadComplianceReport}
                      disabled={loading || !selectedRunId}
                      className="w-full"
                    >
                      {loading ? 'Generating...' : 'Generate Report'}
                    </Button>
                  </div>
                </div>

                {/* Compliance Report */}
                {complianceReport && (
                  <div className="space-y-6">
                    {/* Report Header */}
                    <Card className="bg-gradient-to-r from-green-50 to-emerald-50 border-green-200">
                      <CardContent className="pt-6 space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div>
                            <div className="text-xs text-green-700 font-medium">Run ID</div>
                            <div className="text-lg font-semibold text-green-900">
                              {complianceReport.run_id}
                            </div>
                          </div>
                          <div>
                            <div className="text-xs text-green-700 font-medium">Report Type</div>
                            <div className="text-lg font-semibold text-green-900">
                              {complianceReport.report_type.toUpperCase()}
                            </div>
                          </div>
                          <div>
                            <div className="text-xs text-green-700 font-medium">Generated At</div>
                            <div className="text-lg font-semibold text-green-900">
                              {format(new Date(complianceReport.generated_at), 'MMM dd, yyyy HH:mm:ss')}
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Summary */}
                    <Card className="border-slate-200">
                      <CardHeader>
                        <CardTitle className="text-lg">Summary</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                            <div className="text-2xl font-bold text-blue-900">
                              {complianceReport.summary.total_entries}
                            </div>
                            <div className="text-xs text-blue-700 mt-1">Total Entries</div>
                          </div>
                          <div className="p-4 bg-red-50 rounded-lg border border-red-200">
                            <div className="text-2xl font-bold text-red-900">
                              {complianceReport.summary.critical_count}
                            </div>
                            <div className="text-xs text-red-700 mt-1">Critical</div>
                          </div>
                          <div className="p-4 bg-orange-50 rounded-lg border border-orange-200">
                            <div className="text-2xl font-bold text-orange-900">
                              {complianceReport.summary.error_count}
                            </div>
                            <div className="text-xs text-orange-700 mt-1">Errors</div>
                          </div>
                          <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200">
                            <div className="text-2xl font-bold text-yellow-900">
                              {complianceReport.summary.warning_count}
                            </div>
                            <div className="text-xs text-yellow-700 mt-1">Warnings</div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Detailed Entries */}
                    {complianceReport.entries.length > 0 && (
                      <Card className="border-slate-200">
                        <CardHeader>
                          <CardTitle className="text-lg">Compliance Entries</CardTitle>
                          <CardDescription>
                            {complianceReport.entries.length} entries in this report
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="border border-slate-200 rounded-lg overflow-hidden">
                            <Table>
                              <TableHeader className="bg-slate-50">
                                <TableRow>
                                  <TableHead className="text-xs font-semibold">Timestamp</TableHead>
                                  <TableHead className="text-xs font-semibold">Action</TableHead>
                                  <TableHead className="text-xs font-semibold">Level</TableHead>
                                  <TableHead className="text-xs font-semibold">User</TableHead>
                                  <TableHead className="text-xs font-semibold">IP Address</TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {complianceReport.entries.map((entry) => (
                                  <TableRow key={entry.audit_id} className="hover:bg-slate-50">
                                    <TableCell className="text-xs text-slate-600">
                                      {format(new Date(entry.timestamp), 'MMM dd, HH:mm:ss')}
                                    </TableCell>
                                    <TableCell className="text-xs font-medium text-slate-900">
                                      {entry.action}
                                    </TableCell>
                                    <TableCell className="text-xs">
                                      <Badge className={getLevelColor(entry.level)}>
                                        {entry.level}
                                      </Badge>
                                    </TableCell>
                                    <TableCell className="text-xs text-slate-600">
                                      {entry.user_id || '-'}
                                    </TableCell>
                                    <TableCell className="text-xs text-slate-600">
                                      {entry.ip_address || '-'}
                                    </TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </div>
                        </CardContent>
                      </Card>
                    )}
                  </div>
                )}

                {!complianceReport && !loading && (
                  <div className="text-center py-8 text-slate-500">
                    Select a run ID and report type, then click "Generate Report" to view compliance
                    information
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
