import io
import os
import time
import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

USERNAME = "Verif.AI"
PASSWORD = "Recon"

CSV_TEMPLATE = "RRN,Amount,Tran_Date,RC,Tran_Type,Dr_Cr\n{rrn},{amt},{date},{rc},{tt},{drcr}\n"


def get_token():
    r = client.post("/api/v1/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert r.status_code == 200
    data = r.json()
    assert 'access_token' in data
    return data['access_token']


def test_full_flow_upload_and_recon(tmp_path):
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    # create 7 minimal CSV files in memory
    files = []
    rrn = int(time.time())
    today = "2026-01-03"
    names = [
        'cbs_inward.csv', 'cbs_outward.csv', 'switch.csv', 'npci_inward.csv', 'npci_outward.csv', 'ntsl.csv', 'adjustment.csv'
    ]
    for i, name in enumerate(names):
        content = CSV_TEMPLATE.format(rrn=rrn + i, amt=100 + i, date=today, rc='00', tt='U2', drcr='D')
        files.append(("files", (name, io.BytesIO(content.encode('utf-8')), 'text/csv')))

    params = {'cycle': '1C', 'run_date': today, 'direction': 'INWARD'}
    r = client.post('/api/v1/upload', params=params, files=files, headers=headers)
    assert r.status_code == 201, r.text
    data = r.json()
    run_id = data.get('run_id')
    assert run_id

    # run reconciliation
    r2 = client.post('/api/v1/recon/run', json={'run_id': run_id}, headers=headers)
    assert r2.status_code == 200, r2.text

    # latest summary
    r3 = client.get('/api/v1/recon/latest/summary', headers=headers)
    assert r3.status_code == 200

    # unmatched
    r4 = client.get('/api/v1/recon/latest/unmatched', headers=headers)
    assert r4.status_code == 200

    # hanging
    r5 = client.get('/api/v1/recon/latest/hanging', headers=headers)
    assert r5.status_code == 200

    # enquiry for one rrn
    qrrn = str(rrn)
    r6 = client.get(f'/api/v1/enquiry?rrn={qrrn}', headers=headers)
    # enquiry may return 200 or 404 depending on reconciliation details; assert not server error
    assert r6.status_code in (200, 404)

    # ttum download (may return 200 or 404 depending if ttum files created)
    r7 = client.get(f'/api/v1/reports/ttum?run_id={run_id}', headers=headers)
    assert r7.status_code in (200, 404)

    # cleanup: remove created upload folder
    import shutil
    upload_base = os.path.join(os.path.dirname(__file__), '..', 'data', 'uploads')
    # try to find the run folder under upload_base
    # our FileHandler saves to UPLOAD_DIR; clean any folder starting with run_id
    for root, dirs, files in os.walk(os.path.join(os.path.dirname(__file__), '..')):
        for d in dirs:
            if d == run_id or d.startswith(run_id):
                try:
                    shutil.rmtree(os.path.join(root, d))
                except Exception:
                    pass
