import io
import json
import logging
import os
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/income-expense", tags=["income-expense"])


@router.get("/data")
async def get_income_expense_data(
    date_from: str = Query(..., description="Start date in YYYY-MM-DD format"),
    date_to: str = Query(..., description="End date in YYYY-MM-DD format"),
):
    """
    Get Income & Expense data from NTSL settlement files
    """
    try:
        # Load NTSL settlement data
        ntsl_file = os.path.join("demo_data", "ntsl_settlement.json")

        if not os.path.exists(ntsl_file):
            raise HTTPException(status_code=404, detail="NTSL settlement data not found")

        with open(ntsl_file, 'r') as f:
            ntsl_data = json.load(f)

        # Filter data by date range
        from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
        to_date = datetime.strptime(date_to, "%Y-%m-%d").date()

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

        # Calculate aggregated income and expense
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
            # Income
            u2_payer = record['u2_payer_psp_fees_received']
            u3_payer = record['u3_payer_psp_fees_received']
            beneficiary_u3 = record['beneficiary_u3_approved_fee']
            beneficiary_u3_gst = record['beneficiary_u3_approved_fee_gst']

            income_breakdown['interchange_income']['u2_payer_psp_fees'] += u2_payer
            income_breakdown['interchange_income']['u3_payer_psp_fees'] += u3_payer
            income_breakdown['interchange_income']['beneficiary_u3_fee'] += beneficiary_u3
            income_breakdown['gst_income']['beneficiary_u3_fee_gst'] += beneficiary_u3_gst

            total_income = u2_payer + u3_payer + beneficiary_u3 + beneficiary_u3_gst

            # Expense
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

        # Calculate totals
        total_income = sum(income_breakdown['interchange_income'].values()) + sum(income_breakdown['gst_income'].values())

        total_expense = (
            sum(expense_breakdown['interchange_expense'].values())
            + sum(expense_breakdown['npci_switching_fees'].values())
            + sum(expense_breakdown['gst_expense'].values())
        )

        # Round all values for clean output
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
):
    """
    Download Income & Expense MIS Report as Excel
    """
    try:
        # Load NTSL settlement data
        ntsl_file = os.path.join("demo_data", "ntsl_settlement.json")

        if not os.path.exists(ntsl_file):
            raise HTTPException(status_code=404, detail="NTSL settlement data not found")

        with open(ntsl_file, 'r') as f:
            ntsl_data = json.load(f)

        # Filter data by date range
        from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
        to_date = datetime.strptime(date_to, "%Y-%m-%d").date()

        filtered_data = []
        for record in ntsl_data['settlement_data']:
            record_date = datetime.strptime(record['date'], "%Y-%m-%d").date()
            if from_date <= record_date <= to_date:
                filtered_data.append(record)

        if not filtered_data:
            raise HTTPException(status_code=404, detail="No data found for the selected date range")

        # Prepare data for Excel in the exact format specified
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

        # Create DataFrame
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
