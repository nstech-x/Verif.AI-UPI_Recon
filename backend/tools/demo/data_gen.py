#!/usr/bin/env python3
"""
NPCI / UPI compliant mock data generator for bank reconciliation testing.
Aligned with Verif.ai UPI Functional Document V2 (06-Jan-2026).

Generates reconciliation input files under backend/bank_recon_files using
bank-grade naming conventions:
  cbs_inward.csv
  cbs_outward.csv
  switch.csv
  ISSRP2P<ISSR_BANK><DDMMYY>_<1-10>C.csv
  ISSRP2M<ISSR_BANK><DDMMYY>_<1-10>C.csv
  ACQRP2P<ACQR_BANK><DDMMYY>_<1-10>C.csv
  ACQRP2M<ACQR_BANK><DDMMYY>_<1-10>C.csv
  UPINTSLP<ACQR_BANK><DDMMYYYY>_<1-10>C.csv
  UPIADJReportP<ACQR_BANK><DDMMYY>.csv
  DRCReport<ACQR_BANK><DDMMYY>.csv

Enhancements:
- UPI fields included: UPI_Tran_ID, Payer_PSP, Payee_PSP, MCC, Originating_Channel
- Explicit RC='RB' deemed-success injection
- Hanging simulation: Switch-only transactions missing in NPCI
- Relaxed match: UPI_Tran_ID + Amount match but RRN missing

Requirements:
  pip install pandas openpyxl numpy
"""

import os
import random
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parents[2]

# -------------------------------------------------
# CONFIGURATION
# -------------------------------------------------
OUTPUT_DIR = BACKEND_DIR / "bank_recon_files"
SUBDIRS = {
    "cbs": "cbs",
    "switch": "switch",
    "npci_in_p2p": os.path.join("npci", "inward", "p2p"),
    "npci_in_p2m": os.path.join("npci", "inward", "p2m"),
    "npci_out_p2p": os.path.join("npci", "outward", "p2p"),
    "npci_out_p2m": os.path.join("npci", "outward", "p2m"),
    "ntsl": "ntsl",
    "adjustment": "adjustment",
    "drc": "drc",
}
NUM_MASTER_RECORDS = 300
EXTRA_SWITCH_RECORDS = 12
SEED = 42

RUN_TS = datetime.now()
CYCLE_DATE = RUN_TS.strftime("%Y-%m-%d")
DATE_DDMMYYYY = RUN_TS.strftime("%d%m%Y")
DATE_DDMMYY = RUN_TS.strftime("%d%m%y")
CYCLE_NO = 1
CYCLE_ID = f"{CYCLE_NO}C"
RUN_ID = f"RUN_{RUN_TS.strftime('%Y%m%d_%H%M%S')}"
DIRECTION = "INWARD"

ISSR_BANK = "PYBP"
ACQR_BANK = "PYBL"

random.seed(SEED)
np.random.seed(SEED)

os.makedirs(OUTPUT_DIR, exist_ok=True)
for sub in SUBDIRS.values():
    os.makedirs(OUTPUT_DIR / sub, exist_ok=True)

PAYER_PSP_CHOICES = [
    'GPay', 'PhonePe', 'Paytm', 'BHIM', 'AmazonPay', 'WhatsAppPay',
    'SBI', 'HDFC', 'ICICI', 'AXIS', 'YES'
]
PAYEE_PSP_CHOICES = [
    'SBI', 'HDFC', 'ICICI', 'AXIS', 'YES', 'Kotak', 'BOB', 'IDFC'
]
MCC_CHOICES = ['5411', '5732', '5812', '5999', '6011']
ORIG_CHANNEL_CHOICES = ['MOBILE', 'QR', 'COLLECT', 'INTENT', 'WEB']

# Proportions for special scenarios - Updated for realistic UPI recon
RB_RATIO = 0.06  # ~6% deemed success (RC=RB)
FAILED_RATIO = 0.04  # ~4% failed transactions (RC=05,12)
HANGING_RATIO = 0.08  # ~8% hanging transactions (missing in NPCI)
RELAXED_MATCH_RATIO = 0.02  # ~2% relaxed matches (missing RRN)

# Target distribution: 90% matched, 10% unmatched/exceptions
MATCHED_RATIO = 0.90
UNMATCHED_RATIO = 0.10
HANGING_COUNT_TARGET = 20
RELAXED_MATCH_COUNT_TARGET = 15

# -------------------------------------------------
# HELPERS
# -------------------------------------------------

def generate_unique_rrns(count, forbidden=None):
    """
    Generate unique 12-digit RRNs.
    `forbidden` can be list, set, pandas Series, or None.
    """
    if forbidden is None:
        forbidden_set = set()
    else:
        forbidden_set = set(list(forbidden))

    rrns = set()
    while len(rrns) < count:
        rrn = str(random.randint(100000000000, 999999999999))
        if rrn not in forbidden_set and rrn not in rrns:
            rrns.add(rrn)
    return list(rrns)


def generate_rc(size):
    """Return an array of RC codes with realistic UPI failure distribution."""
    # 00: Success (majority)
    # RB: Deemed success
    # 05, 12: Failures that trigger exception handling
    base = np.random.choice(['00', 'RB', '05', '12'], size=size, p=[0.90, RB_RATIO, FAILED_RATIO/2, FAILED_RATIO/2])
    return base


def rc_to_status(rc):
    return 'SUCCESS' if rc in ('00', 'RB') else 'FAILED'


# -------------------------------------------------
# MASTER DATA
# -------------------------------------------------

def generate_master(n):
    rrns = generate_unique_rrns(n)
    rows = []

    for i in range(n):
        # Create realistic failure scenarios for exception matrix testing
        if i < int(n * 0.02):  # 2% - SUCCESS_SUCCESS_FAILED scenario
            rc = np.random.choice(['05', '12'])  # Failed at NPCI
        elif i < int(n * 0.04):  # 2% - SUCCESS_FAILED_SUCCESS scenario
            rc = '00'  # Will fail at switch later
        elif i < int(n * 0.06):  # 2% - SUCCESS_FAILED_FAILED scenario
            rc = np.random.choice(['05', '12'])  # Failed
        elif i < int(n * 0.08):  # 2% - FAILED_SUCCESS_SUCCESS scenario
            rc = '00'  # Will fail at CBS later
        elif i < int(n * 0.10):  # 2% - FAILED_SUCCESS_FAILED scenario
            rc = np.random.choice(['05', '12'])  # Failed
        else:  # 90% - Mostly successful scenarios
            rc = generate_rc(1)[0]

        amount = round(random.uniform(10, 50000), 2)
        drcr = random.choices(['CR', 'DR'], weights=[0.6, 0.4])[0]
        payer = random.choice(PAYER_PSP_CHOICES)
        payee = random.choice(PAYEE_PSP_CHOICES)
        mcc = random.choice(MCC_CHOICES)
        channel = random.choice(ORIG_CHANNEL_CHOICES)
        txn_subtype = random.choice(["P2P", "P2M"])
        rows.append({
            'Run_ID': RUN_ID,
            'Cycle_ID': CYCLE_ID,
            'UPI_Tran_ID': f"UTRN{100000 + i}",
            'RRN': rrns[i],
            'Amount': amount,
            'Tran_Date': CYCLE_DATE,
            'Transaction_Date': CYCLE_DATE,
            'Date': CYCLE_DATE,
            'Dr_Cr': drcr,
            'Debit_Credit': drcr,
            'RC': rc,
            'Tran_Type': 'U3',  # RAW transactions
            'Status': rc_to_status(rc),
            'Account_No': str(random.randint(1000000000, 9999999999)),
            'Beneficiary': random.choice(['Alice', 'Bob', 'MerchantX', 'CorpY', 'VendorZ']),
            'Payer_PSP': payer,
            'Payee_PSP': payee,
            'MCC': mcc,
            'Originating_Channel': channel,
            'Txn_Subtype': txn_subtype,
            'Source': ''
        })
    return pd.DataFrame(rows)

print('Generating master dataset...')
master = generate_master(NUM_MASTER_RECORDS)

# Assign initial RC pattern to master (so Switch and NPCI can derive)
master['RC'] = generate_rc(len(master))
master['Status'] = master['RC'].apply(rc_to_status)

# -------------------------------------------------
# SWITCH FILE
# -------------------------------------------------
print('Creating Switch file...')
# Switch baseline from master
df_switch = master.copy()
# Add extra Switch-only RRNs to guarantee hanging
extra = generate_master(EXTRA_SWITCH_RECORDS)
extra['RRN'] = generate_unique_rrns(EXTRA_SWITCH_RECORDS, forbidden=df_switch['RRN'])
extra['RC'] = np.random.choice(['00', 'RB', '12', '05'], size=EXTRA_SWITCH_RECORDS, p=[0.65, 0.15, 0.1, 0.1])
extra['Status'] = extra['RC'].apply(rc_to_status)

df_switch = pd.concat([df_switch, extra], ignore_index=True)
# Source tag
df_switch['Source'] = 'SWITCH'

# -------------------------------------------------
# CBS FILES WITH FAILURE SCENARIOS
# -------------------------------------------------
print('Creating CBS Inward / Outward files...')
# Sample based on Dr_Cr with intentional exclusions for exception testing
df_cbs_in = (
    master[master['Dr_Cr'] == 'CR']
    .sample(frac=0.88, random_state=SEED)  # 88% coverage to create missing CBS inward
    .copy()
)
df_cbs_out = (
    master[master['Dr_Cr'] == 'DR']
    .sample(frac=0.85, random_state=SEED)  # 85% coverage to create missing CBS outward
    .copy()
)

df_cbs_in['Source'] = 'CBS'
df_cbs_out['Source'] = 'CBS'

# -------------------------------------------------
# NPCI FILES
# -------------------------------------------------
print('Creating NPCI Inward / Outward files...')
# Start from Switch population to emulate network flow
npc_in = (
    df_switch[df_switch['Dr_Cr'] == 'CR']
    .sample(frac=0.94, random_state=SEED)
    .copy()
)
npc_out = (
    df_switch[df_switch['Dr_Cr'] == 'DR']
    .sample(frac=0.91, random_state=SEED)
    .copy()
)

# Inject RB scenarios explicitly into NPCI to test deemed success
if len(npc_in) > 0:
    rb_idx_in = np.random.choice(npc_in.index, size=max(1, int(len(npc_in) * (RB_RATIO / 2))), replace=False)
    npc_in.loc[rb_idx_in, 'RC'] = 'RB'
if len(npc_out) > 0:
    rb_idx_out = np.random.choice(npc_out.index, size=max(1, int(len(npc_out) * (RB_RATIO / 2))), replace=False)
    npc_out.loc[rb_idx_out, 'RC'] = 'RB'

npc_in['Status'] = npc_in['RC'].apply(rc_to_status)
npc_out['Status'] = npc_out['RC'].apply(rc_to_status)

npc_in['Source'] = 'NPCI'
npc_out['Source'] = 'NPCI'

# -------------------------------------------------
# HANGING SIMULATION (Switch-only subset absent in NPCI)
# -------------------------------------------------
print('Injecting Hanging transactions...')
# Ensure at least HANGING_COUNT_TARGET switch RRNs are not present in NPCI
npc_rrns = set(pd.concat([npc_in['RRN'], npc_out['RRN']]).astype(str))
switch_rrns = set(df_switch['RRN'].astype(str))
missing_in_npci = list(switch_rrns - npc_rrns)
if len(missing_in_npci) < HANGING_COUNT_TARGET:
    # Remove some RRNs from NPCI to reach target
    needed = HANGING_COUNT_TARGET - len(missing_in_npci)
    candidates = list(npc_rrns)
    if candidates:
        drop_rrns = set(np.random.choice(candidates, size=min(needed, len(candidates)), replace=False))
        npc_in = npc_in[~npc_in['RRN'].astype(str).isin(drop_rrns)].copy()
        npc_out = npc_out[~npc_out['RRN'].astype(str).isin(drop_rrns)].copy()

# -------------------------------------------------
# RELAXED MATCH INJECTION (missing RRN but UPI_Tran_ID + Amount match)
# -------------------------------------------------
print('Injecting Relaxed-Match scenarios (missing RRN)...')
# Select subset from master to replicate into Switch with RRN cleared
relaxed_candidates = master.sample(n=min(RELAXED_MATCH_COUNT_TARGET, len(master)), random_state=SEED).copy()
relaxed_key = relaxed_candidates[['UPI_Tran_ID', 'Amount', 'Dr_Cr']].copy()

# For each candidate, find matching rows in switch/npci and clear RRN in one source (e.g., SWITCH)
# to force engine to use relaxed matching
mask = df_switch.set_index(['UPI_Tran_ID', 'Amount', 'Dr_Cr']).index.isin(relaxed_key.set_index(['UPI_Tran_ID', 'Amount', 'Dr_Cr']).index)
idxs = df_switch[mask].sample(frac=1.0, random_state=SEED).index[:len(relaxed_candidates)]
if len(idxs) > 0:
    df_switch.loc[idxs, 'RRN'] = ''

# -------------------------------------------------
# NTSL FILE (SETTLEMENT)
# -------------------------------------------------
print('Creating NTSL file...')
settled = pd.concat([npc_in, npc_out], ignore_index=True)
settled = settled[settled['RC'].isin(['00', 'RB'])].copy()

settled['Settlement_Charge'] = 0.0
settled['Amount_Settled'] = settled['Amount']

charge_idxs = settled.sample(frac=0.03, random_state=SEED).index
for i in charge_idxs:
    charge = round(min(10.0, float(settled.at[i, 'Amount']) * 0.001), 2)
    settled.at[i, 'Settlement_Charge'] = charge
    settled.at[i, 'Amount_Settled'] = round(float(settled.at[i, 'Amount']) - charge, 2)

settled['Source'] = 'NTSL'

# -------------------------------------------------
# WRITE FILES
# -------------------------------------------------
print('Writing output files...')

def _write(df: pd.DataFrame, filename: str, subdir: str = "") -> None:
    target_dir = OUTPUT_DIR / subdir if subdir else OUTPUT_DIR
    os.makedirs(target_dir, exist_ok=True)
    path = target_dir / filename
    if filename.lower().endswith(".xlsx"):
        df.to_excel(path, index=False)
    else:
        df.to_csv(path, index=False)

_write(df_switch, "switch.csv", SUBDIRS["switch"])

# CBS Inward/Outward
# Keep identical schema across all files
common_cols = [
    'Run_ID', 'Cycle_ID', 'UPI_Tran_ID', 'RRN', 'Amount', 'Tran_Date', 'Transaction_Date',
    'Date', 'Dr_Cr', 'Debit_Credit', 'RC', 'Tran_Type', 'Status', 'Account_No', 'Beneficiary',
    'Payer_PSP', 'Payee_PSP', 'MCC', 'Originating_Channel', 'Txn_Subtype', 'Source'
]

df_cbs_in = df_cbs_in[common_cols]
df_cbs_out = df_cbs_out[common_cols]
npc_in = npc_in[common_cols]
npc_out = npc_out[common_cols]
settled_cols = common_cols + ['Settlement_Charge', 'Amount_Settled']
# ensure all required cols exist
for c in ['Settlement_Charge', 'Amount_Settled']:
    if c not in settled.columns:
        settled[c] = ''
settled = settled[settled_cols]

# Write CBS
_write(df_cbs_in, "cbs_inward.csv", SUBDIRS["cbs"])
_write(df_cbs_out, "cbs_outward.csv", SUBDIRS["cbs"])

# Write NPCI in ISSR/ACQR naming with P2P/P2M and 10 cycles
def chunk_df(df: pd.DataFrame, parts: int):
    if df.empty:
        return [df.copy() for _ in range(parts)]
    shuffled = df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    indices = np.array_split(shuffled.index, parts)
    return [shuffled.loc[idx].reset_index(drop=True) for idx in indices]

npc_in_p2p = npc_in[npc_in['Txn_Subtype'] == 'P2P'].copy()
npc_in_p2m = npc_in[npc_in['Txn_Subtype'] == 'P2M'].copy()
npc_out_p2p = npc_out[npc_out['Txn_Subtype'] == 'P2P'].copy()
npc_out_p2m = npc_out[npc_out['Txn_Subtype'] == 'P2M'].copy()

in_p2p_chunks = chunk_df(npc_in_p2p, 10)
in_p2m_chunks = chunk_df(npc_in_p2m, 10)
out_p2p_chunks = chunk_df(npc_out_p2p, 10)
out_p2m_chunks = chunk_df(npc_out_p2m, 10)

for idx in range(10):
    cyc = f"{idx+1}C"
    _write(in_p2p_chunks[idx], f"ISSRP2P{ISSR_BANK}{DATE_DDMMYY}_{cyc}.csv", SUBDIRS["npci_in_p2p"])
    _write(in_p2m_chunks[idx], f"ISSRP2M{ISSR_BANK}{DATE_DDMMYY}_{cyc}.csv", SUBDIRS["npci_in_p2m"])
    _write(out_p2p_chunks[idx], f"ACQRP2P{ACQR_BANK}{DATE_DDMMYY}_{cyc}.csv", SUBDIRS["npci_out_p2p"])
    _write(out_p2m_chunks[idx], f"ACQRP2M{ACQR_BANK}{DATE_DDMMYY}_{cyc}.csv", SUBDIRS["npci_out_p2m"])

# Write NTSL (10 cycles, cycle optional in validation)
ntsl_chunks = chunk_df(settled, 10)
for idx in range(10):
    cyc = f"{idx+1}C"
    ntsl_name = f"UPINTSLP{ACQR_BANK}{DATE_DDMMYYYY}_{cyc}.csv"
    _write(ntsl_chunks[idx], ntsl_name, SUBDIRS["ntsl"])

# -------------------------------------------------
# ADJUSTMENT.CSV - APPLY DURING RECON
# -------------------------------------------------
print('Creating Adjustment.csv file...')
adjustments = []

# Create adjustments for some transactions that would otherwise fail
failed_rrns = master[master['RC'].isin(['05', '12'])].sample(n=min(10, len(master[master['RC'].isin(['05', '12'])])), random_state=SEED)['RRN'].tolist()

for i, rrn in enumerate(failed_rrns[:5]):  # Adjust 5 transactions
    rec = master[master['RRN'] == rrn].iloc[0]
    adjustments.append({
        'Txnuid': f'TXN{i+1}',
        'Uid': f'ADJ{i+1}',
        'Adjdate': CYCLE_DATE,
        'Adjtype': 'FORCE_MATCH',  # Force match failed transactions
        'Remitter': f'Remitter_{i+1}',
        'Beneficiary': f'Beneficiary_{i+1}',
        'Response': 'SUCCESS',
        'RRN': rrn,
        'Amount': rec['Amount'],  # Add required Amount column
        'Tran_Date': CYCLE_DATE,  # Add required Tran_Date column
        'Txnamount': rec['Amount'],
        'Adjamount': rec['Amount'],  # Same amount
        'Fees': round(rec['Amount'] * 0.001, 2),
        'Taxes': round(rec['Amount'] * 0.0005, 2),
        'Compensation amount': 0.0,
        'Transaction_Type': 'UPI',
        'Indicator': 'CREDIT',
        'UPI Transaction ID': rec['UPI_Tran_ID'],
        'Dispute Flag': 'N',
        'Reason Code': 'ADJ001',
        'Payer PSP': rec['Payer_PSP'],
        'Payee PSP': rec['Payee_PSP']
    })

# Add amount correction adjustments
for i, rrn in enumerate(failed_rrns[5:8]):  # Adjust 3 more with amount corrections
    rec = master[master['RRN'] == rrn].iloc[0]
    adj_amount = rec['Amount'] + random.uniform(-100, 100)  # Small adjustment
    adjustments.append({
        'Txnuid': f'TXN{i+6}',
        'Uid': f'ADJ{i+6}',
        'Adjdate': CYCLE_DATE,
        'Adjtype': 'AMOUNT_CORRECTION',
        'Remitter': f'Remitter_{i+6}',
        'Beneficiary': f'Beneficiary_{i+6}',
        'Response': 'SUCCESS',
        'RRN': rrn,
        'Amount': rec['Amount'],  # Add required Amount column
        'Tran_Date': CYCLE_DATE,  # Add required Tran_Date column
        'Txnamount': rec['Amount'],
        'Adjamount': round(adj_amount, 2),
        'Fees': round(abs(adj_amount - rec['Amount']) * 0.001, 2),
        'Taxes': 0.0,
        'Compensation amount': round(abs(adj_amount - rec['Amount']), 2),
        'Transaction_Type': 'UPI',
        'Indicator': 'DEBIT' if adj_amount < rec['Amount'] else 'CREDIT',
        'UPI Transaction ID': rec['UPI_Tran_ID'],
        'Dispute Flag': 'Y',
        'Reason Code': 'ADJ002',
        'Payer PSP': rec['Payer_PSP'],
        'Payee PSP': rec['Payee_PSP']
    })

adj_name = f"UPIADJReportP{ACQR_BANK}{DATE_DDMMYY}.csv"
pd.DataFrame(adjustments).to_csv(OUTPUT_DIR / SUBDIRS["adjustment"] / adj_name, index=False)

# Write DRC report (minimal)
drc_rows = []
for i, rrn in enumerate(failed_rrns[:5]):
    drc_rows.append({
        "RRN": rrn,
        "Reason": "DRC",
        "Amount": float(master[master['RRN'] == rrn].iloc[0]['Amount']),
        "Date": CYCLE_DATE
    })
drc_name = f"DRCReport{ACQR_BANK}{DATE_DDMMYY}.csv"
pd.DataFrame(drc_rows).to_csv(OUTPUT_DIR / SUBDIRS["drc"] / drc_name, index=False)

# -------------------------------------------------
# FINAL CHECKS
# -------------------------------------------------
# Ensure Switch has duplicates with empty RRNs only by design; otherwise RRNs should be unique
non_empty_rrns = df_switch[df_switch['RRN'].astype(str) != '']['RRN']
assert non_empty_rrns.is_unique, "Duplicate non-empty RRNs detected in Switch file!"

print("\nNPCI/UPI compliant mock files generated with realistic exception scenarios")
print("Output directory:", os.path.abspath(OUTPUT_DIR))
for f in sorted(Path(OUTPUT_DIR).rglob("*")):
    if f.is_file():
        rel = f.relative_to(OUTPUT_DIR)
        print(" -", str(rel))
