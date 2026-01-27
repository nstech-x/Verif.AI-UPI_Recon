import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from rollback_manager import RollbackManager, RollbackLevel


def test_ingestion_rollback(tmp_path):
    upload_dir = tmp_path / 'uploads'
    run_id = 'RUN_0001'
    run_folder = upload_dir / run_id
    run_folder.mkdir(parents=True)

    # create a dummy file and mapping
    file_path = run_folder / 'testbad.csv'
    file_path.write_text('bad')
    mapping = {'testbad.csv': 'testbad.csv'}
    with open(run_folder / 'file_mapping.json', 'w') as f:
        import json
        json.dump(mapping, f)

    mgr = RollbackManager(upload_dir=str(upload_dir), output_dir=str(tmp_path / 'out'))
    res = mgr.ingestion_rollback(run_id, 'testbad.csv', 'validation error')
    assert res['status'] == 'success'
    # file should be removed
    assert not os.path.exists(str(file_path))
