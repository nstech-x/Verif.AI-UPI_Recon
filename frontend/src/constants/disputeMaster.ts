/**
 * NPCI/RBI Dispute Master Data
 * Defines valid dispute types, reason codes, lifecycle stages, and TATs
 * Source: UPI Dispute Resolution Framework
 */

import { DisputeMasterEntry } from "../types/dispute";

export const DISPUTE_MASTER: DisputeMasterEntry[] = [
  // U2 - Chargeback Raise (Stage B)
  {
    txnSubtype: "U2",
    category: "Chargeback Raise",
    stageCode: "B",
    reasonCode: "1061",
    reasonDescription: "Credit not processed for cancelled or returned goods and services",
    tatDays: 90,
    tatReference: "Txn Date"
  },
  {
    txnSubtype: "U2",
    category: "Chargeback Raise",
    stageCode: "B",
    reasonCode: "1062",
    reasonDescription: "Paid by alternate means",
    tatDays: 90,
    tatReference: "Txn Date"
  },
  {
    txnSubtype: "U2",
    category: "Chargeback Raise",
    stageCode: "B",
    reasonCode: "1063",
    reasonDescription: "Customer dispute - Goods/Services not as described",
    tatDays: 90,
    tatReference: "Txn Date"
  },
  {
    txnSubtype: "U2",
    category: "Chargeback Raise",
    stageCode: "B",
    reasonCode: "1064",
    reasonDescription: "Customer dispute - Defective goods",
    tatDays: 90,
    tatReference: "Txn Date"
  },
  {
    txnSubtype: "U2",
    category: "Chargeback Raise",
    stageCode: "B",
    reasonCode: "1065",
    reasonDescription: "Customer dispute - Goods not received",
    tatDays: 90,
    tatReference: "Txn Date"
  },
  {
    txnSubtype: "U2",
    category: "Chargeback Raise",
    stageCode: "B",
    reasonCode: "1066",
    reasonDescription: "Services not rendered",
    tatDays: 90,
    tatReference: "Txn Date"
  },
  {
    txnSubtype: "U2",
    category: "Chargeback Raise",
    stageCode: "B",
    reasonCode: "1067",
    reasonDescription: "Recurring transaction cancelled",
    tatDays: 90,
    tatReference: "Txn Date"
  },
  
  // U2 - Chargeback Acceptance (Stage C)
  {
    txnSubtype: "U2",
    category: "Chargeback Acceptance",
    stageCode: "C",
    reasonCode: "1061",
    reasonDescription: "Credit not processed for cancelled or returned goods and services",
    tatDays: 7,
    tatReference: "CB Date"
  },
  {
    txnSubtype: "U2",
    category: "Chargeback Acceptance",
    stageCode: "C",
    reasonCode: "1062",
    reasonDescription: "Paid by alternate means",
    tatDays: 7,
    tatReference: "CB Date"
  },
  
  // U2 - Representment (Stage A)
  {
    txnSubtype: "U2",
    category: "Representment",
    stageCode: "A",
    reasonCode: "1061",
    reasonDescription: "Credit not processed for cancelled or returned goods and services",
    tatDays: 15,
    tatReference: "CB Date"
  },
  {
    txnSubtype: "U2",
    category: "Representment",
    stageCode: "A",
    reasonCode: "1062",
    reasonDescription: "Paid by alternate means",
    tatDays: 15,
    tatReference: "CB Date"
  },
  
  // U2 - Pre-Arbitration Raise (Stage AR)
  {
    txnSubtype: "U2",
    category: "Pre-Arbitration Raise",
    stageCode: "AR",
    reasonCode: "1061",
    reasonDescription: "Credit not processed for cancelled or returned goods and services",
    tatDays: 60,
    tatReference: "Arb Date"
  },
  {
    txnSubtype: "U2",
    category: "Pre-Arbitration Raise",
    stageCode: "AR",
    reasonCode: "1062",
    reasonDescription: "Paid by alternate means",
    tatDays: 60,
    tatReference: "Arb Date"
  },
  
  // U2 - Credit Adjustment
  {
    txnSubtype: "U2",
    category: "Credit Adjustment",
    stageCode: "B",
    reasonCode: "CA01",
    reasonDescription: "Credit adjustment required - Amount discrepancy",
    tatDays: 60,
    tatReference: "Txn Date"
  },
  {
    txnSubtype: "U2",
    category: "Credit Adjustment",
    stageCode: "B",
    reasonCode: "CA02",
    reasonDescription: "Credit adjustment required - Duplicate transaction",
    tatDays: 60,
    tatReference: "Txn Date"
  },
  
  // U3 - Fraud Chargeback Raise (Stage FC)
  {
    txnSubtype: "U3",
    category: "Fraud Chargeback Raise",
    stageCode: "B",
    reasonCode: "U010",
    reasonDescription: "Fraudulent transaction - Card/Account holder denies authorization",
    tatDays: 90,
    tatReference: "Txn Date"
  },
  {
    txnSubtype: "U3",
    category: "Fraud Chargeback Raise",
    stageCode: "B",
    reasonCode: "U011",
    reasonDescription: "Fraudulent transaction - Lost/Stolen credentials",
    tatDays: 90,
    tatReference: "Txn Date"
  },
  {
    txnSubtype: "U3",
    category: "Fraud Chargeback Raise",
    stageCode: "B",
    reasonCode: "U012",
    reasonDescription: "Fraudulent transaction - Account takeover",
    tatDays: 90,
    tatReference: "Txn Date"
  },
  {
    txnSubtype: "U3",
    category: "Fraud Chargeback Raise",
    stageCode: "B",
    reasonCode: "U013",
    reasonDescription: "Unauthorized transaction - No customer consent",
    tatDays: 90,
    tatReference: "Txn Date"
  },
  {
    txnSubtype: "U3",
    category: "Fraud Chargeback Raise",
    stageCode: "B",
    reasonCode: "U014",
    reasonDescription: "Transaction not recognized by customer",
    tatDays: 90,
    tatReference: "Txn Date"
  },
  
  // U3 - Credit Adjustment
  {
    txnSubtype: "U3",
    category: "Credit Adjustment",
    stageCode: "B",
    reasonCode: "U3CA1",
    reasonDescription: "Fraud-related credit adjustment",
    tatDays: 60,
    tatReference: "Txn Date"
  },
  
  // UC - Wrong Credit Raise (Stage WC)
  {
    txnSubtype: "UC",
    category: "Wrong Credit Raise",
    stageCode: "B",
    reasonCode: "WC1",
    reasonDescription: "Wrong credit - Beneficiary mismatch",
    tatDays: 60,
    tatReference: "Txn Date"
  },
  {
    txnSubtype: "UC",
    category: "Wrong Credit Raise",
    stageCode: "B",
    reasonCode: "WC2",
    reasonDescription: "Wrong credit - Amount mismatch",
    tatDays: 60,
    tatReference: "Txn Date"
  },
  {
    txnSubtype: "UC",
    category: "Wrong Credit Raise",
    stageCode: "B",
    reasonCode: "WC3",
    reasonDescription: "Duplicate credit processed",
    tatDays: 60,
    tatReference: "Txn Date"
  },
  {
    txnSubtype: "UC",
    category: "Wrong Credit Raise",
    stageCode: "B",
    reasonCode: "WC4",
    reasonDescription: "Credit to wrong account",
    tatDays: 60,
    tatReference: "Txn Date"
  },
  
  // UC - Credit Adjustment
  {
    txnSubtype: "UC",
    category: "Credit Adjustment",
    stageCode: "B",
    reasonCode: "UCCA1",
    reasonDescription: "Wrong credit adjustment - Reversal required",
    tatDays: 60,
    tatReference: "Txn Date"
  },
  {
    txnSubtype: "UC",
    category: "Credit Adjustment",
    stageCode: "B",
    reasonCode: "UCCA2",
    reasonDescription: "Wrong credit adjustment - Partial reversal",
    tatDays: 60,
    tatReference: "Txn Date"
  }
];

/**
 * Get dispute categories by transaction subtype
 */
export const getDisputeCategories = (txnSubtype: string): string[] => {
  const categories = new Set(
    DISPUTE_MASTER
      .filter(entry => entry.txnSubtype === txnSubtype)
      .map(entry => entry.category)
  );
  return Array.from(categories);
};

/**
 * Get reason codes by transaction subtype and category
 */
export const getReasonCodes = (txnSubtype: string, category: string): DisputeMasterEntry[] => {
  return DISPUTE_MASTER.filter(
    entry => entry.txnSubtype === txnSubtype && entry.category === category
  );
};

/**
 * Get dispute master entry by reason code
 */
export const getDisputeMasterEntry = (reasonCode: string): DisputeMasterEntry | undefined => {
  return DISPUTE_MASTER.find(entry => entry.reasonCode === reasonCode);
};