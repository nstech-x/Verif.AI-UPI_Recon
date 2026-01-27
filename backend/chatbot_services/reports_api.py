"""
Report Download API - Maps frontend report IDs to actual files
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os
from pathlib import Path

router = APIRouter()

# Base directory for reports
REPORTS_BASE_DIR = Path(__file__).parent.parent.parent / "RUN_20260108_023831"

# Mapping of frontend report IDs to actual file paths (using existing files)
REPORT_FILE_MAPPING = {
    # Listing Reports (Raw Files) - Using available files as substitutes
    "listing/cbs_beneficiary": "reports/GL_vs_Switch_Inward.csv",
    "listing/cbs_remitter": "reports/GL_vs_Switch_Outward.csv",
    "listing/switch_inward": "reports/Switch_vs_NPCI_Inward.csv",
    "listing/switch_outward": "reports/Switch_vs_NPCI_Outward.csv",
    "listing/npci_inward": "reports/GL_vs_NPCI_Inward.csv",
    "listing/npci_outward": "reports/GL_vs_NPCI_Outward.csv",
    
    # Reconciliation Reports - Inward (using actual files)
    "reconciliation/inward/gl_switch_matched_inward": "reports/GL_vs_Switch_Inward.csv",
    "reconciliation/inward/gl_switch_unmatched_inward": "reports/Unmatched_Inward_Ageing.csv",
    "reconciliation/inward/switch_network_matched_inward": "reports/Switch_vs_NPCI_Inward.csv",
    "reconciliation/inward/switch_network_unmatched_inward": "reports/Unmatched_Inward_Ageing.csv",
    "reconciliation/inward/gl_network_matched_inward": "reports/GL_vs_NPCI_Inward.csv",
    "reconciliation/inward/gl_network_unmatched_inward": "reports/Unmatched_Inward_Ageing.csv",
    "reconciliation/inward/hanging_transactions_inward": "reports/unmatched_exceptions.csv",
    
    # Reconciliation Reports - Outward (using actual files)
    "reconciliation/outward/gl_switch_matched_outward": "reports/GL_vs_Switch_Outward.csv",
    "reconciliation/outward/gl_switch_unmatched_outward": "reports/Unmatched_Outward_Ageing.csv",
    "reconciliation/outward/switch_network_matched_outward": "reports/Switch_vs_NPCI_Outward.csv",
    "reconciliation/outward/switch_network_unmatched_outward": "reports/Unmatched_Outward_Ageing.csv",
    "reconciliation/outward/gl_network_matched_outward": "reports/GL_vs_NPCI_Outward.csv",
    "reconciliation/outward/gl_network_unmatched_outward": "reports/Unmatched_Outward_Ageing.csv",
    "reconciliation/outward/hanging_transactions_outward": "reports/unmatched_exceptions.csv",
    
    # TTUM & Annexure (using actual files)
    "ttum_annexure/consolidated/ttum_consolidated": "ttum_csv_RUN_20260108_023831_20260108_025617.zip",
    "ttum_annexure/annexures/annexure_i": "reports/ANNEXURE_I.csv",
    "ttum_annexure/annexures/annexure_ii": "reports/ANNEXURE_II.csv",
    "ttum_annexure/annexures/annexure_iii": "reports/ANNEXURE_III.csv",
    "ttum_annexure/annexures/annexure_iv": "reports/ANNEXURE_IV.xlsx",
    
    # RBI Regulatory (using available files as substitutes)
    "rbi_regulatory/settlement/daily_settlement": "reports/ANNEXURE_I.xlsx",
    "rbi_regulatory/settlement/npci_clearing": "reports/ANNEXURE_I.xlsx",
    "rbi_regulatory/aging/unmatched_aging": "reports/Unmatched_Inward_Ageing.csv",
    "rbi_regulatory/disputes/dispute_summary": "reports/unmatched_exceptions.csv",
    
    # Legacy Reports (using actual files)
    "legacy/matched_json": "recon_output.json",
    "legacy/unmatched_json": "recon_output.json",
    "legacy/summary_json": "recon_output.json",
    "legacy/matched_csv": "reports/GL_vs_NPCI_Inward.csv",
    "legacy/unmatched_csv": "reports/unmatched_exceptions.csv",
}


@router.get("/api/v1/reports/{report_path:path}")
async def download_report(report_path: str):
    """
    Download a report file based on the report path.
    
    Args:
        report_path: The report path from frontend (e.g., "reconciliation/inward/gl_switch_matched_inward")
    
    Returns:
        FileResponse with the actual report file
    """
    # Clean up the path
    report_path = report_path.strip("/")
    
    # Get the mapped file path
    if report_path not in REPORT_FILE_MAPPING:
        raise HTTPException(
            status_code=404, 
            detail=f"Report not found: {report_path}. Available reports: {list(REPORT_FILE_MAPPING.keys())}"
        )
    
    file_path = REPORTS_BASE_DIR / REPORT_FILE_MAPPING[report_path]
    
    # Check if file exists
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Report file not found on disk: {file_path}"
        )
    
    # Determine media type based on file extension
    media_type_map = {
        ".csv": "text/csv",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".json": "application/json",
        ".pdf": "application/pdf",
        ".zip": "application/zip",
    }
    
    file_ext = file_path.suffix.lower()
    media_type = media_type_map.get(file_ext, "application/octet-stream")
    
    # Return the file
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name
    )