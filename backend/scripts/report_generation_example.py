"""Small example to demonstrate report generation for one run and cycle.

Run: python backend/scripts/report_generation_example.py
"""
import os
from datetime import datetime
from recon_engine import ReconciliationEngine


def make_example_results():
    # minimal results dict matching recon output structure
    now = datetime.now().strftime('%Y-%m-%d')
    return {
        '518221608885': {
            'cbs': {'amount': 150.00, 'date': now, 'dr_cr': 'C', 'rc': '00', 'tran_type': 'INWARD'},
            'switch': {'amount': 150.00, 'date': now, 'dr_cr': 'C', 'rc': '00', 'tran_type': 'INWARD'},
            'npci': {'amount': 150.00, 'date': now, 'dr_cr': '', 'rc': '00', 'tran_type': 'INWARD'},
            'status': 'MATCHED'
        },
        '518221608884': {
            'cbs': {'amount': 200.50, 'date': now, 'dr_cr': 'D', 'rc': '00', 'tran_type': 'OUTWARD'},
            'switch': None,
            'npci': {'amount': 200.50, 'date': now, 'dr_cr': '', 'rc': 'RB01', 'tran_type': 'OUTWARD'},
            'status': 'ORPHAN',
            'hanging_reason': 'declined_with_reversal'
        }
    }


def main():
    run_id = 'RUN_EXAMPLE_001'
    cycle_id = '1A'
    base = os.path.join('data', 'output', run_id)
    os.makedirs(base, exist_ok=True)

    engine = ReconciliationEngine(output_dir='data/output')
    results = make_example_results()

    # Generate matched pair CSVs
    engine.generate_report(results, base, run_id=run_id, cycle_id=cycle_id)

    # Generate ageing and hanging
    engine.generate_unmatched_ageing(results, base, run_id=run_id, cycle_id=cycle_id)
    engine.generate_hanging_reports(results, base, run_id=run_id, cycle_id=cycle_id)

    # Generate annexure candidates
    engine.generate_adjustments_csv(results, base, run_id=run_id, cycle_id=cycle_id)

    print('Example reports generated under', base)


if __name__ == '__main__':
    main()
