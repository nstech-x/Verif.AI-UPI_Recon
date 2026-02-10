import json
import os
from datetime import datetime, date
from typing import Dict, List, Optional

import pandas as pd

from config import OUTPUT_DIR, UPLOAD_DIR
from services.annexure_iv import generate_annexure_iv_csv


def _resolve_latest_run() -> str:
    runs = [d for d in os.listdir(UPLOAD_DIR) if d.startswith("RUN_")]
    if not runs:
        raise FileNotFoundError("No runs found in upload directory")
    return sorted(runs)[-1]


def resolve_run_id(run_id: Optional[str]) -> str:
    return run_id or _resolve_latest_run()


def _reports_dir(run_id: str) -> str:
    path = os.path.join(OUTPUT_DIR, run_id, "reports")
    os.makedirs(path, exist_ok=True)
    return path


def _load_json(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_run_metadata(run_id: str) -> Dict:
    meta_path = os.path.join(UPLOAD_DIR, run_id, "metadata.json")
    if os.path.exists(meta_path):
        return _load_json(meta_path)
    return {}

def get_uploaded_files(run_id: str, file_type: str) -> List[str]:
    """Return absolute paths for uploaded files of a given type from metadata."""
    meta = get_run_metadata(run_id)
    saved_files = meta.get("saved_files", {})
    entry = saved_files.get(file_type)
    if not entry:
        return []
    filenames = entry if isinstance(entry, list) else [entry]
    paths = []
    for name in filenames:
        candidate = os.path.join(UPLOAD_DIR, run_id, name)
        if os.path.exists(candidate):
            paths.append(candidate)
    return paths


def _find_saved_file(run_id: str, file_type: str) -> Optional[str]:
    meta = get_run_metadata(run_id)
    saved_files = meta.get("saved_files", {})
    entry = saved_files.get(file_type)
    if not entry:
        return None
    if isinstance(entry, list):
        filename = entry[0]
    else:
        filename = entry
    path = os.path.join(UPLOAD_DIR, run_id, filename)
    return path if os.path.exists(path) else None


def _read_df(path: str) -> pd.DataFrame:
    if path.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path)


def _write_csv(run_id: str, filename: str, df: pd.DataFrame) -> str:
    out_path = os.path.join(_reports_dir(run_id), filename)
    df.to_csv(out_path, index=False, encoding="utf-8")
    return out_path


def get_recon_output(run_id: str) -> Dict:
    output_path = os.path.join(OUTPUT_DIR, run_id, "recon_output.json")
    if os.path.exists(output_path):
        return _load_json(output_path)
    return {}


def _get_demo_data_path(*parts: str) -> str:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools", "demo", "demo_data"))
    return os.path.join(base, *parts)


def get_ntsl_settlement_path() -> Optional[str]:
    candidates = [
        _get_demo_data_path("ntsl_settlement.json"),
        os.path.abspath(os.path.join(os.getcwd(), "demo_data", "ntsl_settlement.json")),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def get_dispute_data_path() -> Optional[str]:
    candidates = [
        _get_demo_data_path("disputes.json"),
        os.path.abspath(os.path.join(os.getcwd(), "demo_data", "disputes.json")),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def generate_listing_report(run_id: str, file_type: str, direction: Optional[str] = None) -> Optional[str]:
    """Generate a CSV listing report from uploaded raw files."""
    file_path = _find_saved_file(run_id, file_type)
    if not file_path:
        return None

    df = _read_df(file_path)
    if direction:
        dir_upper = direction.upper()
        # Attempt to filter using common debit/credit or direction columns
        for col in ["Dr_Cr", "dr_cr", "Debit_Credit", "debit_credit", "Direction", "direction"]:
            if col in df.columns:
                if dir_upper == "INWARD":
                    df = df[df[col].astype(str).str.upper().str.startswith("C")]
                elif dir_upper == "OUTWARD":
                    df = df[df[col].astype(str).str.upper().str.startswith("D")]
                break

    filename = f"{file_type}_{direction.lower() if direction else 'raw'}.csv"
    return _write_csv(run_id, filename, df)


def generate_matched_transactions_report(run_id: str) -> Optional[str]:
    reports_dir = _reports_dir(run_id)
    for name in ["matched_transactions.csv", "matched.csv"]:
        candidate = os.path.join(reports_dir, name)
        if os.path.exists(candidate):
            return candidate
    return None


def generate_unmatched_transactions_report(run_id: str) -> Optional[str]:
    reports_dir = _reports_dir(run_id)
    for name in ["unmatched_exceptions.csv", "unmatched.csv"]:
        candidate = os.path.join(reports_dir, name)
        if os.path.exists(candidate):
            return candidate
    return None


def generate_adjustment_listing(run_id: str) -> Optional[str]:
    # adjustments.csv is written under OUTPUT_DIR/<run_id> (root) by recon engine
    candidate = os.path.join(OUTPUT_DIR, run_id, "adjustments.csv")
    if os.path.exists(candidate):
        return candidate
    data = get_recon_output(run_id)
    exceptions = data.get("exceptions", [])
    ttum_candidates = data.get("ttum_candidates", [])
    rows = []
    for exc in exceptions:
        rows.append({
            "rrn": exc.get("rrn", ""),
            "status": "EXCEPTION",
            "source": exc.get("source", ""),
            "amount": exc.get("amount", ""),
            "exception_type": exc.get("exception_type", ""),
            "ttum_required": exc.get("ttum_required", False),
            "ttum_type": exc.get("ttum_type", ""),
            "direction": exc.get("direction", ""),
        })
    for ttum in ttum_candidates:
        rows.append({
            "rrn": ttum.get("rrn", ""),
            "status": "TTUM_REQUIRED",
            "source": ttum.get("source", ""),
            "amount": ttum.get("amount", ""),
            "exception_type": ttum.get("exception_type", ""),
            "ttum_required": True,
            "ttum_type": ttum.get("ttum_type", ""),
            "direction": ttum.get("direction", ""),
        })
    df = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["rrn", "status", "source", "amount", "exception_type", "ttum_required", "ttum_type", "direction"]
    )
    return _write_csv(run_id, "adjustments.csv", df)


def generate_ttum_listing(run_id: str, direction: str) -> Optional[str]:
    data = get_recon_output(run_id)
    ttum_candidates = data.get("ttum_candidates", [])
    rows = []
    for entry in ttum_candidates:
        if str(entry.get("direction", "")).upper() != direction.upper():
            continue
        rows.append(entry)
    if not rows:
        # write empty file with headers
        df = pd.DataFrame(columns=["source", "direction", "rrn", "amount", "ttum_type", "exception_type", "gl_accounts"])
    else:
        df = pd.DataFrame(rows)
    filename = f"ttum_listing_{direction.lower()}.csv"
    return _write_csv(run_id, filename, df)


def _derive_annexure_flag(exc: Dict) -> Optional[str]:
    exc_type = str(exc.get("exception_type", "")).upper()
    if "TCC" in exc_type or exc_type.startswith("RB"):
        return "TCC"
    if "RET" in exc_type or "RETURN" in exc_type or "TIMEOUT" in exc_type or "NPCI_FAILED" in exc_type:
        return "RET"
    if "MISMATCH" in exc_type or "PARTIAL" in exc_type:
        return "RRC"
    if "ORPHAN" in exc_type or "UNMATCHED" in exc_type:
        return "DRC"
    # fallback: use debit/credit if present
    drcr = str(exc.get("debit_credit", "")).upper()
    if drcr.startswith("C"):
        return "Cr Adj"
    if drcr.startswith("D"):
        return "DRC"
    return None


def generate_annexure_iv_split(run_id: str) -> Dict[str, Optional[str]]:
    """Generate Annexure-IV files split into (TCC+RET) and (DRC+RRC)."""
    data = get_recon_output(run_id)
    exceptions = data.get("exceptions", [])
    tcc_ret = []
    drc_rrc = []
    for exc in exceptions:
        flag = _derive_annexure_flag(exc)
        if not flag:
            continue
        rrn = str(exc.get("rrn", "")).strip()
        if not rrn:
            continue
        amount = exc.get("amount", None)
        if amount is None or str(amount).strip() == "":
            continue
        date_value = str(exc.get("date", "")).strip()
        if not date_value:
            date_value = datetime.utcnow().strftime("%Y-%m-%d")
        record = {
            "Bankadjref": f"BR_{flag}_{rrn}_{int(datetime.now().timestamp())}",
            "Flag": flag,
            "shtdat": date_value[:10],
            "adjsmt": amount,
            "Shser": rrn,
            "Shcrd": f"NBIN{rrn}",
            "FileName": f"ANNEXURE_{run_id}.csv",
            "reason": str(exc.get("exception_type", ""))[:5],
            "specifyother": str(exc.get("exception_type", ""))[:400],
        }
        if flag in {"TCC", "RET"}:
            tcc_ret.append(record)
        else:
            drc_rrc.append(record)

    annex_dir = os.path.join(OUTPUT_DIR, run_id, "annexure")
    os.makedirs(annex_dir, exist_ok=True)

    outputs: Dict[str, Optional[str]] = {"tcc_ret": None, "drc_rrc": None}
    if tcc_ret:
        out_path = os.path.join(annex_dir, f"ANNEXURE_IV_TCC_RET_{run_id}.csv")
        generate_annexure_iv_csv(tcc_ret, output_path=out_path)
        outputs["tcc_ret"] = out_path
    if drc_rrc:
        out_path = os.path.join(annex_dir, f"ANNEXURE_IV_DRC_RRC_{run_id}.csv")
        generate_annexure_iv_csv(drc_rrc, output_path=out_path)
        outputs["drc_rrc"] = out_path
    return outputs


def _load_ntsl_data() -> List[Dict]:
    ntsl_path = get_ntsl_settlement_path()
    if not ntsl_path:
        return []
    data = _load_json(ntsl_path)
    return data.get("settlement_data", [])


def generate_mis_report(run_id: str, period: str, date_from: Optional[str], date_to: Optional[str]) -> Optional[str]:
    rows = _load_ntsl_data()
    if not rows:
        df = pd.DataFrame(columns=["period", "interchange_income", "interchange_expense", "gst_income", "gst_expense", "net_position"])
        return _write_csv(run_id, f"mis_{period}.csv", df)

    def parse_date(value: str) -> date:
        return datetime.strptime(value, "%Y-%m-%d").date()

    if date_from and date_to:
        start = parse_date(date_from)
        end = parse_date(date_to)
        rows = [r for r in rows if start <= parse_date(r["date"]) <= end]

    def bucket_key(d: date) -> str:
        if period == "daily":
            return d.strftime("%Y-%m-%d")
        if period == "weekly":
            year, week, _ = d.isocalendar()
            return f"{year}-W{week:02d}"
        if period == "monthly":
            return d.strftime("%Y-%m")
        return d.strftime("%Y-%m-%d")

    grouped: Dict[str, Dict[str, float]] = {}
    for r in rows:
        d = parse_date(r["date"])
        key = bucket_key(d)
        rec = grouped.setdefault(key, {
            "interchange_income": 0.0,
            "interchange_expense": 0.0,
            "gst_income": 0.0,
            "gst_expense": 0.0,
        })
        rec["interchange_income"] += (
            r["u2_payer_psp_fees_received"]
            + r["u3_payer_psp_fees_received"]
            + r["beneficiary_u3_approved_fee"]
        )
        rec["gst_income"] += r["beneficiary_u3_approved_fee_gst"]
        rec["interchange_expense"] += (
            r["remitter_u2_approved_fee"]
            + r["remitter_u3_approved_fee"]
            + r["remitter_p2a_declined"]
            + r["remitter_u2_npci_switching_fee"]
            + r["remitter_u3_npci_switching_fee"]
        )
        rec["gst_expense"] += (
            r["remitter_u2_approved_fee_gst"]
            + r["remitter_u3_approved_fee_gst"]
            + r["remitter_u2_npci_switching_fee_gst"]
            + r["remitter_u3_npci_switching_fee_gst"]
        )

    output = []
    for key, totals in grouped.items():
        net = (totals["interchange_income"] + totals["gst_income"]) - (totals["interchange_expense"] + totals["gst_expense"])
        output.append({
            "period": key,
            **{k: round(v, 2) for k, v in totals.items()},
            "net_position": round(net, 2),
        })

    df = pd.DataFrame(output)
    return _write_csv(run_id, f"mis_{period}.csv", df)


def generate_datewise_income_expense(run_id: str, date_from: Optional[str], date_to: Optional[str]) -> Optional[str]:
    rows = _load_ntsl_data()
    if not rows:
        df = pd.DataFrame(columns=["date", "income", "expense", "net", "transaction_count"])
        return _write_csv(run_id, "income_expense_datewise.csv", df)

    def parse_date(value: str) -> date:
        return datetime.strptime(value, "%Y-%m-%d").date()

    if date_from and date_to:
        start = parse_date(date_from)
        end = parse_date(date_to)
        rows = [r for r in rows if start <= parse_date(r["date"]) <= end]

    output = []
    for r in rows:
        income = (
            r["u2_payer_psp_fees_received"]
            + r["u3_payer_psp_fees_received"]
            + r["beneficiary_u3_approved_fee"]
            + r["beneficiary_u3_approved_fee_gst"]
        )
        expense = (
            r["remitter_u2_approved_fee"]
            + r["remitter_u3_approved_fee"]
            + r["remitter_p2a_declined"]
            + r["remitter_u2_npci_switching_fee"]
            + r["remitter_u3_npci_switching_fee"]
            + r["remitter_u2_approved_fee_gst"]
            + r["remitter_u3_approved_fee_gst"]
            + r["remitter_u2_npci_switching_fee_gst"]
            + r["remitter_u3_npci_switching_fee_gst"]
        )
        output.append({
            "date": r["date"],
            "income": round(income, 2),
            "expense": round(expense, 2),
            "net": round(income - expense, 2),
            "transaction_count": r["transaction_count"],
        })

    df = pd.DataFrame(output)
    return _write_csv(run_id, "income_expense_datewise.csv", df)


def generate_monthly_settlement_report(run_id: str) -> Optional[str]:
    rows = _load_ntsl_data()
    if not rows:
        df = pd.DataFrame(columns=["month", "approved_transaction_amount", "transaction_count"])
        return _write_csv(run_id, "monthly_settlement_ntsl_extract.csv", df)

    grouped: Dict[str, Dict[str, float]] = {}
    for r in rows:
        month = r["date"][:7]
        rec = grouped.setdefault(month, {"approved_transaction_amount": 0.0, "transaction_count": 0})
        rec["approved_transaction_amount"] += r.get("approved_transaction_amount", 0)
        rec["transaction_count"] += r.get("transaction_count", 0)

    output = [{"month": k, **v} for k, v in grouped.items()]
    df = pd.DataFrame(output)
    return _write_csv(run_id, "monthly_settlement_ntsl_extract.csv", df)


def generate_ntsl_settlement_ttum(run_id: str, bank_type: str) -> Optional[str]:
    rows = _load_ntsl_data()
    if not rows:
        df = pd.DataFrame(columns=["date", "bank_type", "dr_cr", "amount", "narration"])
        return _write_csv(run_id, f"ntsl_settlement_ttum_{bank_type.lower()}.csv", df)

    output = []
    for r in rows:
        if bank_type.lower() == "sponsor":
            amount = (
                r["remitter_u2_approved_fee"]
                + r["remitter_u3_approved_fee"]
                + r["remitter_p2a_declined"]
                + r["remitter_u2_npci_switching_fee"]
                + r["remitter_u3_npci_switching_fee"]
                + r["remitter_u2_approved_fee_gst"]
                + r["remitter_u3_approved_fee_gst"]
                + r["remitter_u2_npci_switching_fee_gst"]
                + r["remitter_u3_npci_switching_fee_gst"]
            )
            output.append({
                "date": r["date"],
                "bank_type": "Sponsor",
                "dr_cr": "D",
                "amount": round(amount, 2),
                "narration": "NTSL settlement payable (fees + GST)",
            })
        else:
            amount = (
                r["u2_payer_psp_fees_received"]
                + r["u3_payer_psp_fees_received"]
                + r["beneficiary_u3_approved_fee"]
                + r["beneficiary_u3_approved_fee_gst"]
            )
            output.append({
                "date": r["date"],
                "bank_type": "Sub-Member",
                "dr_cr": "C",
                "amount": round(amount, 2),
                "narration": "NTSL settlement receivable (fees + GST)",
            })

    df = pd.DataFrame(output)
    return _write_csv(run_id, f"ntsl_settlement_ttum_{bank_type.lower()}.csv", df)


def generate_dispute_tracker(run_id: str) -> Optional[str]:
    disputes_path = get_dispute_data_path()
    if not disputes_path:
        df = pd.DataFrame(columns=["id", "rrn", "amount", "status", "raised_date", "reason", "assigned_to"])
        return _write_csv(run_id, "dispute_tracker.csv", df)
    data = _load_json(disputes_path)
    df = pd.DataFrame(data.get("disputes", []))
    return _write_csv(run_id, "dispute_tracker.csv", df)


def generate_rbi_reporting(run_id: str) -> Optional[str]:
    recon = get_recon_output(run_id)
    summary = recon.get("summary", {})
    ntsl_rows = _load_ntsl_data()
    total_income = 0.0
    total_expense = 0.0
    for r in ntsl_rows:
        total_income += (
            r["u2_payer_psp_fees_received"]
            + r["u3_payer_psp_fees_received"]
            + r["beneficiary_u3_approved_fee"]
            + r["beneficiary_u3_approved_fee_gst"]
        )
        total_expense += (
            r["remitter_u2_approved_fee"]
            + r["remitter_u3_approved_fee"]
            + r["remitter_p2a_declined"]
            + r["remitter_u2_npci_switching_fee"]
            + r["remitter_u3_npci_switching_fee"]
            + r["remitter_u2_approved_fee_gst"]
            + r["remitter_u3_approved_fee_gst"]
            + r["remitter_u2_npci_switching_fee_gst"]
            + r["remitter_u3_npci_switching_fee_gst"]
        )

    df = pd.DataFrame([{
        "run_id": run_id,
        "report_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "total_transactions": summary.get("total_cbs", 0) + summary.get("total_switch", 0) + summary.get("total_npci", 0),
        "matched": summary.get("matched_cbs", 0) + summary.get("matched_switch", 0) + summary.get("matched_npci", 0),
        "unmatched": summary.get("unmatched_cbs", 0) + summary.get("unmatched_switch", 0) + summary.get("unmatched_npci", 0),
        "ttum_required": summary.get("ttum_required", 0),
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "net_position": round(total_income - total_expense, 2),
    }])
    return _write_csv(run_id, "rbi_reporting.csv", df)


def find_gl_statement(run_id: str) -> Optional[str]:
    # Prefer OUTPUT_DIR/<run_id>/reports/gl_statement.csv
    candidate = os.path.join(OUTPUT_DIR, run_id, "reports", "gl_statement.csv")
    if os.path.exists(candidate):
        return candidate
    # fallback to output gl_statement folder
    out_gl = os.path.join(OUTPUT_DIR, run_id, "gl_statement")
    if os.path.exists(out_gl):
        for f in os.listdir(out_gl):
            if f.endswith((".csv", ".xlsx")):
                return os.path.join(out_gl, f)
    # fallback to upload folder
    up_gl = os.path.join(UPLOAD_DIR, run_id, "gl_statement")
    if os.path.exists(up_gl):
        for f in os.listdir(up_gl):
            if f.endswith((".csv", ".xlsx")):
                return os.path.join(up_gl, f)
    return None
