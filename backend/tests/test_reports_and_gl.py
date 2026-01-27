import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from recon_engine import ReconciliationEngine


def test_pairwise_reports_and_gl(tmp_path):
    run_folder = tmp_path / 'RUN_TEST'
    run_folder.mkdir()
    # prepare results
    results = {
        'R1': {'cbs': {'amount': 100, 'date': '2025-12-01'}, 'switch': {'amount': 100, 'date': '2025-12-01'}, 'npci': {'amount': 100, 'date': '2025-12-01'}, 'status': 'MATCHED'},
        'R2': {'cbs': {'amount': 200, 'date': '2025-12-02'}, 'switch': None, 'npci': {'amount': 200, 'date': '2025-12-02'}, 'status': 'PARTIAL_MATCH'}
    }
    engine = ReconciliationEngine()
    # call generate_report
    r = engine.generate_report(results, str(run_folder), run_id='RUN_TEST')
    # check reports
    reports_dir = os.path.join(str(run_folder), 'reports')
    assert os.path.exists(os.path.join(reports_dir, 'gl_switch.csv'))
    assert os.path.exists(os.path.join(reports_dir, 'switch_npci.csv'))
    assert os.path.exists(os.path.join(reports_dir, 'gl_npci.csv'))