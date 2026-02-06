import os
from typing import List, Optional

import pandas as pd

from config import OUTPUT_DIR, UPLOAD_DIR


def get_ttum_files(run_id: str, cycle_id: Optional[str] = None, format: str = 'all') -> List[str]:
    """Get TTUM files for a run"""
    ttum_files = []

    # Check OUTPUT_DIR
    output_ttum = os.path.join(OUTPUT_DIR, run_id, 'ttum')
    if cycle_id:
        output_ttum = os.path.join(OUTPUT_DIR, run_id, f'cycle_{cycle_id}', 'ttum')

    if os.path.exists(output_ttum):
        for f in os.listdir(output_ttum):
            if format == 'all':
                if f.endswith(('.csv', '.xlsx', '.json')):
                    ttum_files.append(os.path.join(output_ttum, f))
            elif format == 'csv' and f.endswith('.csv'):
                ttum_files.append(os.path.join(output_ttum, f))
            elif format == 'xlsx' and f.endswith('.xlsx'):
                ttum_files.append(os.path.join(output_ttum, f))

    # Check UPLOAD_DIR as fallback
    if not ttum_files:
        upload_ttum = os.path.join(UPLOAD_DIR, run_id, 'ttum')
        if cycle_id:
            upload_ttum = os.path.join(UPLOAD_DIR, run_id, f'cycle_{cycle_id}', 'ttum')

        if os.path.exists(upload_ttum):
            for f in os.listdir(upload_ttum):
                if format == 'all':
                    if f.endswith(('.csv', '.xlsx', '.json')):
                        ttum_files.append(os.path.join(upload_ttum, f))
                elif format == 'csv' and f.endswith('.csv'):
                    ttum_files.append(os.path.join(upload_ttum, f))
                elif format == 'xlsx' and f.endswith('.xlsx'):
                    ttum_files.append(os.path.join(upload_ttum, f))

    return ttum_files


def write_ttum_csv(run_id: str, cycle_id: Optional[str], filename: str, headers: List[str], data: List[dict]) -> str:
    """Write TTUM data to CSV"""
    output_dir = os.path.join(OUTPUT_DIR, run_id, 'ttum')
    if cycle_id:
        output_dir = os.path.join(OUTPUT_DIR, run_id, f'cycle_{cycle_id}', 'ttum')

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{filename}.csv")

    df = pd.DataFrame(data, columns=headers)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')

    return output_path


def write_ttum_xlsx(run_id: str, cycle_id: Optional[str], filename: str, headers: List[str], data: List[dict]) -> str:
    """Write TTUM data to XLSX"""
    output_dir = os.path.join(OUTPUT_DIR, run_id, 'ttum')
    if cycle_id:
        output_dir = os.path.join(OUTPUT_DIR, run_id, f'cycle_{cycle_id}', 'ttum')

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{filename}.xlsx")

    df = pd.DataFrame(data, columns=headers)
    df.to_excel(output_path, index=False, engine='openpyxl')

    return output_path
