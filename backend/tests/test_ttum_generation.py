import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from settlement_engine import SettlementEngine

def test_ttum_generation(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    engine = SettlementEngine(str(out))

    # prepare simple recon_results
    recon = {
        'R1': {'status': 'ORPHAN', 'cbs': {'amount': 100, 'date': '2025-12-01', 'dr_cr': 'D', 'rc': '00', 'tran_type': 'U2'}},
        'R2': {'status': 'MATCHED', 'npci': {'amount': 200, 'date': '2025-12-02', 'dr_cr': 'C', 'rc': 'RB01', 'tran_type': 'U3'}}
    }

    created = engine.generate_ttum_files(recon, str(out))
    # ensure files created
    assert 'tcc' in {os.path.basename(p)[:-4].lower() for p in created.values()}
    for k, v in created.items():
        assert os.path.exists(v)
    # index.json exists
    idx = os.path.join(str(out), 'ttum', 'index.json')
    assert os.path.exists(idx)
