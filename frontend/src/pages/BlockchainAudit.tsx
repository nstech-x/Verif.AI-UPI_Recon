import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Separator } from "../components/ui/separator";
import { 
  Shield, 
  Link as LinkIcon, 
  CheckCircle, 
  Hash,
  Clock,
  User,
  FileText
} from "lucide-react";

// Mock blockchain data
const AUDIT_TRAIL = [
  {
    eventId: "EVT001234",
    timestamp: "2026-01-14T09:54:30Z",
    eventType: "reconciliation_completed",
    runId: "RUN_20260114_095430",
    user: "Verif.AI",
    hash: "a7f5d9c3e8b2f4a1c6d8e9f2b3c5d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4",
    prevHash: "b8e6c0d4f9a3e5b2d7c9f0e1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1",
    anchored: true,
    blockNumber: 125678,
    details: {
      totalTransactions: 3256,
      matched: 2987,
      unmatched: 189
    }
  },
  {
    eventId: "EVT001235",
    timestamp: "2026-01-14T10:15:22Z",
    eventType: "force_match_approved",
    rrn: "636397811101710",
    user: "checker1",
    maker: "maker1",
    hash: "c9f6d1e5a3b4f7c2d8e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2",
    prevHash: "a7f5d9c3e8b2f4a1c6d8e9f2b3c5d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4",
    anchored: true,
    blockNumber: 125679,
    details: {
      action: "force_match",
      amount: 12300.00,
      approvalStatus: "approved"
    }
  },
  {
    eventId: "EVT001236",
    timestamp: "2026-01-14T11:30:45Z",
    eventType: "dispute_raised",
    disputeId: "DSP001235",
    user: "maker1",
    hash: "d0a7e2f6b4c5d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3",
    prevHash: "c9f6d1e5a3b4f7c2d8e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2",
    anchored: true,
    blockNumber: 125680,
    details: {
      rrn: "636397811101711",
      reason: "Transaction not found in Switch"
    }
  }
];

const INTEGRITY_STATUS = {
  totalEvents: 125680,
  verifiedBlocks: 125680,
  failedVerifications: 0,
  lastAudit: "2026-01-14T12:00:00Z",
  blockchainNetwork: "Hyperledger Fabric",
  consensusAlgorithm: "PBFT"
};

export default function BlockchainAudit() {
  const formatEventType = (type: string) => {
    return type.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString('en-IN', {
      dateStyle: 'medium',
      timeStyle: 'short'
    });
  };

  const truncateHash = (hash: string) => {
    return `${hash.substring(0, 12)}...${hash.substring(hash.length - 12)}`;
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-foreground flex items-center gap-2">
              <Shield className="w-6 h-6 text-brand-blue" />
              Audit & Integrity Ledger
            </h1>
            <Badge className="bg-green-100 text-green-800 border-green-300">
              <CheckCircle className="w-3 h-3 mr-1" />
              Blockchain Anchored
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Immutable audit trail with blockchain verification
          </p>
        </div>
      </div>

      {/* Integrity Status */}
      <Card className="bg-gradient-to-r from-blue-50 to-purple-50 border-2">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="w-5 h-5" />
            System Integrity Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="space-y-1">
              <div className="text-sm text-muted-foreground">Total Events</div>
              <div className="text-2xl font-bold">{INTEGRITY_STATUS.totalEvents.toLocaleString()}</div>
            </div>
            <div className="space-y-1">
              <div className="text-sm text-muted-foreground">Verified Blocks</div>
              <div className="text-2xl font-bold text-green-600">{INTEGRITY_STATUS.verifiedBlocks.toLocaleString()}</div>
            </div>
            <div className="space-y-1">
              <div className="text-sm text-muted-foreground">Failed Verifications</div>
              <div className="text-2xl font-bold text-red-600">{INTEGRITY_STATUS.failedVerifications}</div>
            </div>
            <div className="space-y-1">
              <div className="text-sm text-muted-foreground">Network</div>
              <div className="text-base font-semibold">{INTEGRITY_STATUS.blockchainNetwork}</div>
            </div>
          </div>
          <Separator className="my-4" />
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <div>
              <strong>Consensus:</strong> {INTEGRITY_STATUS.consensusAlgorithm}
            </div>
            <div>
              <strong>Last Audit:</strong> {formatTimestamp(INTEGRITY_STATUS.lastAudit)}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Event Timeline */}
      <Card>
        <CardHeader>
          <CardTitle>Audit Event Timeline</CardTitle>
          <CardDescription>Chronological record of all system events</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {AUDIT_TRAIL.map((event, idx) => (
              <div key={event.eventId} className="relative">
                {/* Timeline connector */}
                {idx < AUDIT_TRAIL.length - 1 && (
                  <div className="absolute left-[11px] top-10 w-0.5 h-full bg-border" />
                )}
                
                <div className="flex gap-4">
                  {/* Timeline dot */}
                  <div className="flex-shrink-0 mt-1">
                    <div className="w-6 h-6 rounded-full bg-brand-blue flex items-center justify-center">
                      <div className="w-2 h-2 rounded-full bg-white" />
                    </div>
                  </div>

                  {/* Event card */}
                  <Card className="flex-1 border-2">
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between">
                        <div className="space-y-1">
                          <CardTitle className="text-base">
                            {formatEventType(event.eventType)}
                          </CardTitle>
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Clock className="w-3 h-3" />
                            {formatTimestamp(event.timestamp)}
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-1">
                          <Badge variant="outline" className="text-xs">
                            Block #{event.blockNumber}
                          </Badge>
                          {event.anchored && (
                            <Badge className="bg-green-100 text-green-800 border-green-300 text-xs">
                              <LinkIcon className="w-3 h-3 mr-1" />
                              Anchored
                            </Badge>
                          )}
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {/* Event details */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-muted-foreground" />
                          <span className="text-muted-foreground">Event ID:</span>
                          <span className="font-mono">{event.eventId}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <User className="w-4 h-4 text-muted-foreground" />
                          <span className="text-muted-foreground">User:</span>
                          <span className="font-medium">{event.user}</span>
                        </div>
                        {event.runId && (
                          <div className="flex items-center gap-2 col-span-2">
                            <span className="text-muted-foreground">Run ID:</span>
                            <span className="font-mono text-xs">{event.runId}</span>
                          </div>
                        )}
                      </div>

                      {/* Hashes */}
                      <div className="space-y-2 bg-muted/30 rounded p-3">
                        <div className="flex items-start gap-2 text-xs">
                          <Hash className="w-3 h-3 text-muted-foreground mt-0.5" />
                          <div className="flex-1 space-y-1">
                            <div className="text-muted-foreground">Current Hash:</div>
                            <div className="font-mono break-all">{truncateHash(event.hash)}</div>
                          </div>
                        </div>
                        <div className="flex items-start gap-2 text-xs">
                          <LinkIcon className="w-3 h-3 text-muted-foreground mt-0.5" />
                          <div className="flex-1 space-y-1">
                            <div className="text-muted-foreground">Previous Hash:</div>
                            <div className="font-mono break-all">{truncateHash(event.prevHash)}</div>
                          </div>
                        </div>
                      </div>

                      {/* Additional details */}
                      {event.details && (
                        <div className="bg-blue-50 border border-blue-200 rounded p-3 text-sm">
                          <div className="font-medium mb-1">Event Details:</div>
                          <div className="space-y-0.5 text-xs">
                            {Object.entries(event.details).map(([key, value]) => (
                              <div key={key}>
                                <span className="text-muted-foreground capitalize">
                                  {key.replace(/([A-Z])/g, ' $1').trim()}:
                                </span>{' '}
                                <span className="font-medium">
                                  {typeof value === 'number' ? value.toLocaleString() : value}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}