/**
 * Demo Dispute Data Generator
 * Generates realistic dispute data for demo mode
 */

import { Dispute, DisputeStageCode, TxnSubtype, stageToStatusGroup } from "../types/dispute";
import { DISPUTE_MASTER } from "../constants/disputeMaster";

/**
 * Generate demo disputes across various stages and categories
 */
export const generateDemoDisputes = (): Dispute[] => {
  const disputes: Dispute[] = [];
  const today = new Date();
  
  // Generate 50 disputes with varied characteristics
  for (let i = 0; i < 50; i++) {
    // Random master entry
    const masterEntry = DISPUTE_MASTER[Math.floor(Math.random() * DISPUTE_MASTER.length)];
    
    // Random stage (simulate lifecycle)
    const stages: DisputeStageCode[] = ["B", "C", "A", "AR", "ACA", "D", "ACC", "REV", "WTH", "VER"];
    const stageCode = stages[Math.floor(Math.random() * stages.length)];
    
    // Generate dates
    const daysAgo = Math.floor(Math.random() * 90);
    const createdDate = new Date(today);
    createdDate.setDate(createdDate.getDate() - daysAgo);
    
    const updatedDate = new Date(createdDate);
    updatedDate.setDate(updatedDate.getDate() + Math.floor(Math.random() * daysAgo));
    
    // Generate transaction details
    const txnDate = new Date(createdDate);
    txnDate.setDate(txnDate.getDate() - Math.floor(Math.random() * 30));
    
    const amount = 500 + Math.random() * 49500;
    
    disputes.push({
      disputeId: `DIS${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, '0')}${String(1000 + i).slice(-4)}`,
      txnSubtype: masterEntry.txnSubtype,
      disputeCategory: masterEntry.category,
      stageCode: stageCode,
      reasonCode: masterEntry.reasonCode,
      reasonDescription: masterEntry.reasonDescription,
      tatDays: masterEntry.tatDays,
      tatReference: masterEntry.tatReference,
      statusGroup: stageToStatusGroup(stageCode),
      createdAt: createdDate.toISOString(),
      updatedAt: updatedDate.toISOString(),
      transactionRRN: `${txnDate.getFullYear()}${String(txnDate.getMonth() + 1).padStart(2, '0')}${String(txnDate.getDate()).padStart(2, '0')}${String(100000 + i).slice(-6)}`,
      transactionAmount: amount,
      transactionDate: txnDate.toISOString()
    });
  }
  
  return disputes;
};

/**
 * Get dispute statistics
 */
export const getDisputeStats = (disputes: Dispute[]) => {
  const total = disputes.length;
  const byStatus = {
    open: disputes.filter(d => d.statusGroup === "Open").length,
    working: disputes.filter(d => d.statusGroup === "Working").length,
    closed: disputes.filter(d => d.statusGroup === "Closed").length
  };
  
  const byCategory = disputes.reduce((acc, d) => {
    acc[d.disputeCategory] = (acc[d.disputeCategory] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  
  const bySubtype = disputes.reduce((acc, d) => {
    acc[d.txnSubtype] = (acc[d.txnSubtype] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  
  // Calculate TAT status (simplified for demo)
  const tatStatus = {
    withinTAT: Math.floor(total * 0.7),
    approachingTAT: Math.floor(total * 0.2),
    tatBreached: Math.floor(total * 0.1)
  };
  
  return {
    total,
    byStatus,
    byCategory,
    bySubtype,
    tatStatus
  };
};