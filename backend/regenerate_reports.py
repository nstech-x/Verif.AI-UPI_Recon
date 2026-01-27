"""
Regenerate reports for existing reconciliation runs
This script reads existing recon_output.json and generates all missing reports
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(__file__))

from config import OUTPUT_DIR
from recon_engine import ReconciliationEngine

def regenerate_reports(run_id):
    """Regenerate all reports for a given run_id"""
    print(f"Regenerating reports for {run_id}...")
    
    # Check if recon_output.json exists
    recon_output_path = os.path.join(OUTPUT_DIR, run_id, 'recon_output.json')
    if not os.path.exists(recon_output_path):
        print(f"[ERROR] No recon_output.json found for {run_id}")
        return False
    
    # Load results
    with open(recon_output_path, 'r') as f:
        results = json.load(f)
    
    # Check if this is UPI format
    if isinstance(results, dict) and 'summary' in results:
        print("[OK] Detected UPI format results")
        
        # Initialize recon engine
        recon_engine = ReconciliationEngine(output_dir=OUTPUT_DIR)
        
        # Generate reports
        output_run_dir = os.path.join(OUTPUT_DIR, run_id)
        try:
            recon_engine.generate_upi_report(results, output_run_dir, run_id=run_id)
            print(f"[OK] Reports generated successfully in {output_run_dir}/reports")
            return True
        except Exception as e:
            print(f"[ERROR] Error generating reports: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print("[WARNING] Legacy format detected - report regeneration not supported")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_id = sys.argv[1]
    else:
        # Use latest run
        runs = [d for d in os.listdir(OUTPUT_DIR) if d.startswith('RUN_')]
        if not runs:
            print("[ERROR] No runs found")
            sys.exit(1)
        run_id = sorted(runs)[-1]
        print(f"Using latest run: {run_id}")
    
    success = regenerate_reports(run_id)
    sys.exit(0 if success else 1)
