import io
import json
import logging
import os
from datetime import datetime
from typing import Optional

import pandas as pd

from services.report_catalog import get_ntsl_settlement_path, resolve_run_id, get_uploaded_files
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/income-expense", tags=["income-expense"])


@router.get("/data")
async def get_income_expense_data(
    date_from: str = Query(..., description="Start date in YYYY-MM-DD format"),
    date_to: str = Query(..., description="End date in YYYY-MM-DD format"),
    run_id: Optional[str] = Query(None, description="Optional run id"),
):
    """
    Get Income & Expense data from NTSL settlement files
    """
    try:
        # Prefer real-time NTSL CSVs from latest run
        run_id = resolve_run_id(run_id)
        ntsl_files = get_uploaded_files(run_id, "ntsl")

        from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
        to_date = datetime.strptime(date_to, "%Y-%m-%d").date()

        if ntsl_files:
            frames = []
            for path in ntsl_files:
                try:
                    frames.append(pd.read_csv(path))
                except Exception as e:
                    logger.warning(f"Failed to read NTSL file {path}: {e}")
            if not frames:
                raise HTTPException(status_code=404, detail="NTSL settlement data not found")

            df = pd.concat(frames, ignore_index=True)
            # normalize columns
            date_col = None
            for col in ["Date", "Tran_Date", "Transaction_Date"]:
                if col in df.columns:
                    date_col = col
                    break
            if not date_col:
                raise HTTPException(status_code=400, detail="NTSL data missing date column")

            drcr_col = "Dr_Cr" if "Dr_Cr" in df.columns else ("Debit_Credit" if "Debit_Credit" in df.columns else None)
            fee_col = "Settlement_Charge" if "Settlement_Charge" in df.columns else None
            if fee_col is None:
                df["Settlement_Charge"] = 0.0
                fee_col = "Settlement_Charge"

            df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.date
            df = df[(df[date_col] >= from_date) & (df[date_col] <= to_date)]

            if df.empty:
                return JSONResponse(content={
                    "status": "success",
                    "data": [],
                    "summary": {
                        "total_income": 0,
                        "total_expense": 0,
                        "net_position": 0,
                    },
                })

            df[fee_col] = pd.to_numeric(df[fee_col], errors="coerce").fillna(0.0)
            df["gst"] = (df[fee_col] * 0.18).round(2)

            def is_credit(val: str) -> bool:
                if val is None:
                    return True
                v = str(val).upper()
                return v.startswith("C") or v.startswith("CR")

            if drcr_col:
                df["is_credit"] = df[drcr_col].apply(is_credit)
            else:
                df["is_credit"] = True

            df["income_fee"] = df.apply(lambda r: r[fee_col] if r["is_credit"] else 0.0, axis=1)
            df["expense_fee"] = df.apply(lambda r: r[fee_col] if not r["is_credit"] else 0.0, axis=1)
            df["income_gst"] = df.apply(lambda r: r["gst"] if r["is_credit"] else 0.0, axis=1)
            df["expense_gst"] = df.apply(lambda r: r["gst"] if not r["is_credit"] else 0.0, axis=1)

            grouped = df.groupby(date_col).agg(
                income=("income_fee", "sum"),
                expense=("expense_fee", "sum"),
                income_gst=("income_gst", "sum"),
                expense_gst=("expense_gst", "sum"),
                transaction_count=("RRN", "count") if "RRN" in df.columns else ("UPI_Tran_ID", "count"),
            ).reset_index()

            date_wise_data = []
            for _, row in grouped.iterrows():
                income = float(row["income"] + row["income_gst"])
                expense = float(row["expense"] + row["expense_gst"])
                date_wise_data.append({
                    "date": row[date_col].strftime("%Y-%m-%d"),
                    "income": round(income, 2),
                    "expense": round(expense, 2),
                    "net": round(income - expense, 2),
                    "transaction_count": int(row["transaction_count"]),
                })

            total_income = float(grouped["income"].sum() + grouped["income_gst"].sum())
            total_expense = float(grouped["expense"].sum() + grouped["expense_gst"].sum())

            income_breakdown = {
                "interchange_income": {
                    "u2_payer_psp_fees": round(float(grouped["income"].sum()), 2),
                    "u3_payer_psp_fees": 0.0,
                    "beneficiary_u3_fee": 0.0,
                },
                "gst_income": {
                    "beneficiary_u3_fee_gst": round(float(grouped["income_gst"].sum()), 2),
                },
            }

            expense_breakdown = {
                "interchange_expense": {
                    "remitter_u2_fee": round(float(grouped["expense"].sum()), 2),
                    "remitter_u3_fee": 0.0,
                    "remitter_p2a_declined": 0.0,
                },
                "npci_switching_fees": {
                    "remitter_u2_npci": 0.0,
                    "remitter_u3_npci": 0.0,
                },
                "gst_expense": {
                    "remitter_u2_fee_gst": round(float(grouped["expense_gst"].sum()), 2),
                    "remitter_u3_fee_gst": 0.0,
                    "remitter_u2_npci_gst": 0.0,
                    "remitter_u3_npci_gst": 0.0,
                },
            }

            return JSONResponse(content={
                "status": "success",
                "date_from": date_from,
                "date_to": date_to,
                "summary": {
                    "total_income": round(total_income, 2),
                    "total_expense": round(total_expense, 2),
                    "net_position": round(total_income - total_expense, 2),
                },
                "income_breakdown": income_breakdown,
                "expense_breakdown": expense_breakdown,
                "date_wise_data": date_wise_data,
            })

        # Fallback to demo NTSL settlement data
        ntsl_file = get_ntsl_settlement_path()
        if not ntsl_file or not os.path.exists(ntsl_file):
            raise HTTPException(status_code=404, detail="NTSL settlement data not found")

        with open(ntsl_file, 'r') as f:
            ntsl_data = json.load(f)

        # Filter data by date range
        filtered_data = []
        for record in ntsl_data['settlement_data']:
            record_date = datetime.strptime(record['date'], "%Y-%m-%d").date()
            if from_date <= record_date <= to_date:
                filtered_data.append(record)

        if not filtered_data:
            return JSONResponse(content={
                "status": "success",
                "data": [],
                "summary": {
                    "total_income": 0,
                    "total_expense": 0,
                    "net_position": 0,
                },
            })

        # Calculate aggregated income and expense (demo)
        income_breakdown = {
            "interchange_income": {
                "u2_payer_psp_fees": 0,
                "u3_payer_psp_fees": 0,
                "beneficiary_u3_fee": 0,
            },
            "gst_income": {
                "beneficiary_u3_fee_gst": 0,
            },
        }

        expense_breakdown = {
            "interchange_expense": {
                "remitter_u2_fee": 0,
                "remitter_u3_fee": 0,
                "remitter_p2a_declined": 0,
            },
            "npci_switching_fees": {
                "remitter_u2_npci": 0,
                "remitter_u3_npci": 0,
            },
            "gst_expense": {
                "remitter_u2_fee_gst": 0,
                "remitter_u3_fee_gst": 0,
                "remitter_u2_npci_gst": 0,
                "remitter_u3_npci_gst": 0,
            },
        }

        date_wise_data = []
        for record in filtered_data:
            u2_payer = record['u2_payer_psp_fees_received']
            u3_payer = record['u3_payer_psp_fees_received']
            beneficiary_u3 = record['beneficiary_u3_approved_fee']
            beneficiary_u3_gst = record['beneficiary_u3_approved_fee_gst']

            income_breakdown['interchange_income']['u2_payer_psp_fees'] += u2_payer
            income_breakdown['interchange_income']['u3_payer_psp_fees'] += u3_payer
            income_breakdown['interchange_income']['beneficiary_u3_fee'] += beneficiary_u3
            income_breakdown['gst_income']['beneficiary_u3_fee_gst'] += beneficiary_u3_gst

            total_income = u2_payer + u3_payer + beneficiary_u3 + beneficiary_u3_gst

            rem_u2_fee = record['remitter_u2_approved_fee']
            rem_u3_fee = record['remitter_u3_approved_fee']
            rem_p2a = record['remitter_p2a_declined']
            rem_u2_npci = record['remitter_u2_npci_switching_fee']
            rem_u3_npci = record['remitter_u3_npci_switching_fee']
            rem_u2_fee_gst = record['remitter_u2_approved_fee_gst']
            rem_u3_fee_gst = record['remitter_u3_approved_fee_gst']
            rem_u2_npci_gst = record['remitter_u2_npci_switching_fee_gst']
            rem_u3_npci_gst = record['remitter_u3_npci_switching_fee_gst']

            expense_breakdown['interchange_expense']['remitter_u2_fee'] += rem_u2_fee
            expense_breakdown['interchange_expense']['remitter_u3_fee'] += rem_u3_fee
            expense_breakdown['interchange_expense']['remitter_p2a_declined'] += rem_p2a
            expense_breakdown['npci_switching_fees']['remitter_u2_npci'] += rem_u2_npci
            expense_breakdown['npci_switching_fees']['remitter_u3_npci'] += rem_u3_npci
            expense_breakdown['gst_expense']['remitter_u2_fee_gst'] += rem_u2_fee_gst
            expense_breakdown['gst_expense']['remitter_u3_fee_gst'] += rem_u3_fee_gst
            expense_breakdown['gst_expense']['remitter_u2_npci_gst'] += rem_u2_npci_gst
            expense_breakdown['gst_expense']['remitter_u3_npci_gst'] += rem_u3_npci_gst

            total_expense = (
                rem_u2_fee
                + rem_u3_fee
                + rem_p2a
                + rem_u2_npci
                + rem_u3_npci
                + rem_u2_fee_gst
                + rem_u3_fee_gst
                + rem_u2_npci_gst
                + rem_u3_npci_gst
            )

            date_wise_data.append({
                "date": record['date'],
                "income": round(total_income, 2),
                "expense": round(total_expense, 2),
                "net": round(total_income - total_expense, 2),
                "transaction_count": record['transaction_count'],
            })

        total_income = sum(income_breakdown['interchange_income'].values()) + sum(income_breakdown['gst_income'].values())
        total_expense = (
            sum(expense_breakdown['interchange_expense'].values())
            + sum(expense_breakdown['npci_switching_fees'].values())
            + sum(expense_breakdown['gst_expense'].values())
        )

        for category in income_breakdown:
            for key in income_breakdown[category]:
                income_breakdown[category][key] = round(income_breakdown[category][key], 2)

        for category in expense_breakdown:
            for key in expense_breakdown[category]:
                expense_breakdown[category][key] = round(expense_breakdown[category][key], 2)

        return JSONResponse(content={
            "status": "success",
            "date_from": date_from,
            "date_to": date_to,
            "summary": {
                "total_income": round(total_income, 2),
                "total_expense": round(total_expense, 2),
                "net_position": round(total_income - total_expense, 2),
            },
            "income_breakdown": income_breakdown,
            "expense_breakdown": expense_breakdown,
            "date_wise_data": date_wise_data,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Income/Expense data error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get income/expense data: {str(e)}")


@router.get("/download-excel")
async def download_income_expense_excel(
    date_from: str = Query(..., description="Start date in YYYY-MM-DD format"),
    date_to: str = Query(..., description="End date in YYYY-MM-DD format"),
    run_id: Optional[str] = Query(None, description="Optional run id"),
):
    """
    Download Income & Expense MIS Report as Excel
    """
    try:
        run_id = resolve_run_id(run_id)
        ntsl_files = get_uploaded_files(run_id, "ntsl")

        from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
        to_date = datetime.strptime(date_to, "%Y-%m-%d").date()

        if ntsl_files:
            frames = []
            for path in ntsl_files:
                try:
                    frames.append(pd.read_csv(path))
                except Exception as e:
                    logger.warning(f"Failed to read NTSL file {path}: {e}")
            if not frames:
                raise HTTPException(status_code=404, detail="NTSL settlement data not found")

            df = pd.concat(frames, ignore_index=True)
            date_col = None
            for col in ["Date", "Tran_Date", "Transaction_Date"]:
                if col in df.columns:
                    date_col = col
                    break
            if not date_col:
                raise HTTPException(status_code=400, detail="NTSL data missing date column")

            drcr_col = "Dr_Cr" if "Dr_Cr" in df.columns else ("Debit_Credit" if "Debit_Credit" in df.columns else None)
            fee_col = "Settlement_Charge" if "Settlement_Charge" in df.columns else None
            if fee_col is None:
                df["Settlement_Charge"] = 0.0
                fee_col = "Settlement_Charge"

            df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.date
            df = df[(df[date_col] >= from_date) & (df[date_col] <= to_date)]

            if df.empty:
                raise HTTPException(status_code=404, detail="No data found for the selected date range")

            df[fee_col] = pd.to_numeric(df[fee_col], errors="coerce").fillna(0.0)
            df["gst"] = (df[fee_col] * 0.18).round(2)

            def is_credit(val: str) -> bool:
                if val is None:
                    return True
                v = str(val).upper()
                return v.startswith("C") or v.startswith("CR")

            if drcr_col:
                df["is_credit"] = df[drcr_col].apply(is_credit)
            else:
                df["is_credit"] = True

            df["income_fee"] = df.apply(lambda r: r[fee_col] if r["is_credit"] else 0.0, axis=1)
            df["expense_fee"] = df.apply(lambda r: r[fee_col] if not r["is_credit"] else 0.0, axis=1)
            df["income_gst"] = df.apply(lambda r: r["gst"] if r["is_credit"] else 0.0, axis=1)
            df["expense_gst"] = df.apply(lambda r: r["gst"] if not r["is_credit"] else 0.0, axis=1)

            grouped = df.groupby(date_col).agg(
                interchange_income=("income_fee", "sum"),
                interchange_expense=("expense_fee", "sum"),
                gst_income=("income_gst", "sum"),
                gst_expense=("expense_gst", "sum"),
                transaction_count=("RRN", "count") if "RRN" in df.columns else ("UPI_Tran_ID", "count"),
            ).reset_index()

            grouped["net_position"] = (grouped["interchange_income"] + grouped["gst_income"]) - (grouped["interchange_expense"] + grouped["gst_expense"])

            excel_data = []
            for _, row in grouped.iterrows():
                excel_data.append({
                    "Date": row[date_col].strftime("%Y-%m-%d"),
                    "Interchange Income": round(float(row["interchange_income"]), 2),
                    "Interchange Expense": round(float(row["interchange_expense"]), 2),
                    "GST Income": round(float(row["gst_income"]), 2),
                    "GST Expense": round(float(row["gst_expense"]), 2),
                    "Net Position": round(float(row["net_position"]), 2),
                    "Transaction Count": int(row["transaction_count"]),
                })

            df = pd.DataFrame(excel_data)
        else:
            # Load demo settlement data
            ntsl_file = get_ntsl_settlement_path()
            if not ntsl_file or not os.path.exists(ntsl_file):
                raise HTTPException(status_code=404, detail="NTSL settlement data not found")

            with open(ntsl_file, 'r') as f:
                ntsl_data = json.load(f)

            filtered_data = []
            for record in ntsl_data['settlement_data']:
                record_date = datetime.strptime(record['date'], "%Y-%m-%d").date()
                if from_date <= record_date <= to_date:
                    filtered_data.append(record)

            if not filtered_data:
                raise HTTPException(status_code=404, detail="No data found for the selected date range")

            excel_data = []
            for record in filtered_data:
                excel_data.append({
                    "Date": record['date'],
                    "Remitter U2 Approved Fee": record['remitter_u2_approved_fee'],
                    "Remitter U2 Approved Fee GST": record['remitter_u2_approved_fee_gst'],
                    "Remitter U2 NPCI Switching Fee": record['remitter_u2_npci_switching_fee'],
                    "Remitter U2 NPCI Switching Fee GST": record['remitter_u2_npci_switching_fee_gst'],
                    "Remitter U3 Approved Fee": record['remitter_u3_approved_fee'],
                    "Remitter U3 Approved Fee GST": record['remitter_u3_approved_fee_gst'],
                    "Remitter U3 NPCI Switching Fee": record['remitter_u3_npci_switching_fee'],
                    "Remitter U3 NPCI Switching Fee GST": record['remitter_u3_npci_switching_fee_gst'],
                    "Remitter P2A Declined": record['remitter_p2a_declined'],
                    "U2 Payer PSP Fees Received": record['u2_payer_psp_fees_received'],
                    "U3 Payer PSP Fees Received": record['u3_payer_psp_fees_received'],
                    "Beneficiary U3 Approved Fee": record['beneficiary_u3_approved_fee'],
                    "Beneficiary U3 Approved Fee GST": record['beneficiary_u3_approved_fee_gst'],
                })

            df = pd.DataFrame(excel_data)

        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Income_Expense_MIS', index=False)

        output.seek(0)

        # Generate filename with date range
        filename = f"Income_Expense_MIS_Report_{date_from}_to_{date_to}.xlsx"

        # Return as file download
        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Excel download error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel report: {str(e)}")
