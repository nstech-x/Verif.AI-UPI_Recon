/**
 * Dispute Data Model - NPCI/RBI Compliant
 * Reflects real dispute terminology and lifecycle
 */

export type TxnSubtype = "U2" | "U3" | "UC";

export type DisputeStatusGroup = "Open" | "Working" | "Closed";

export type DisputeStageCode = 
  | "B"      // Chargeback Raise
  | "C"      // Chargeback Acceptance
  | "A"      // Representment
  | "AR"     // Pre-Arbitration
  | "ACA"    // Arbitration
  | "D"      // Deferred
  | "ACC"    // Accepted
  | "REV"    // Reversed
  | "WTH"    // Withdrawn
  | "VER";   // Verdict

export interface Dispute {
  disputeId: string;
  txnSubtype: TxnSubtype;
  disputeCategory: string;
  stageCode: DisputeStageCode;
  reasonCode: string;
  reasonDescription: string;
  tatDays: number;
  tatReference: string;
  statusGroup: DisputeStatusGroup;
  createdAt: string;
  updatedAt: string;
  transactionRRN?: string;
  transactionAmount?: number;
  transactionDate?: string;
}

export interface DisputeMasterEntry {
  txnSubtype: TxnSubtype;
  category: string;
  stageCode: DisputeStageCode;
  reasonCode: string;
  reasonDescription: string;
  tatDays: number;
  tatReference: string;
}

/**
 * Map internal stage codes to UI status groups
 */
export const stageToStatusGroup = (stage: DisputeStageCode): DisputeStatusGroup => {
  switch (stage) {
    case "B":      // Raise
    case "C":      // Acceptance
    case "A":      // Representment
      return "Open";
    
    case "AR":     // Pre-Arbitration
    case "ACA":    // Arbitration
    case "D":      // Deferred
      return "Working";
    
    case "ACC":    // Accepted
    case "REV":    // Reversed
    case "WTH":    // Withdrawn
    case "VER":    // Verdict
      return "Closed";
    
    default:
      return "Open";
  }
};

/**
 * Get human-readable stage name
 */
export const getStageName = (stage: DisputeStageCode): string => {
  const names: Record<DisputeStageCode, string> = {
    B: "Chargeback Raise",
    C: "Chargeback Acceptance",
    A: "Representment",
    AR: "Pre-Arbitration",
    ACA: "Arbitration",
    D: "Deferred",
    ACC: "Accepted",
    REV: "Reversed",
    WTH: "Withdrawn",
    VER: "Verdict"
  };
  return names[stage] || stage;
};