import io
import time
import requests

BASE = "http://127.0.0.1:8000"
USERNAME = "Verif.AI"
PASSWORD = "Recon"

def get_token():
    r = requests.post(f"{BASE}/api/v1/auth/login", json={"username": USERNAME, "password": PASSWORD})
    print('login status', r.status_code)
    print(r.text)
    r.raise_for_status()
    return r.json()['access_token']

CSV_TEMPLATE = "RRN,Amount,Tran_Date,RC,Tran_Type,Dr_Cr\n{rrn},{amt},{date},{rc},{tt},{drcr}\n"

if __name__ == '__main__':
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    rrn = int(time.time())
    today = time.strftime('%Y-%m-%d')
    names = [
        'cbs_inward.csv', 'cbs_outward.csv', 'switch.csv', 'npci_inward.csv', 'npci_outward.csv', 'ntsl.csv', 'adjustment.csv'
    ]

    files = []
    for i, name in enumerate(names):
        content = CSV_TEMPLATE.format(rrn=rrn + i, amt=100 + i, date=today, rc='00', tt='U2', drcr='D')
        bio = io.BytesIO(content.encode('utf-8'))
        # requests accepts (filename, fileobj, content_type)
        files.append(('files', (name, bio, 'text/csv')))

    params = {'cycle': '1C', 'run_date': today, 'direction': 'INWARD'}
    print('Uploading...')
    r = requests.post(f"{BASE}/api/v1/upload", params=params, files=files, headers=headers)
    print('upload status', r.status_code)
    try:
        print(r.json())
    except Exception:
        print(r.text)
    r.raise_for_status()

    run_id = r.json().get('run_id')
    print('Uploaded run_id:', run_id)

    # trigger reconciliation
    print('Triggering recon run...')
    r2 = requests.post(f"{BASE}/api/v1/recon/run", json={'run_id': run_id}, headers=headers)
    print('recon status', r2.status_code)
    try:
        print(r2.json())
    except Exception:
        print(r2.text)
    r2.raise_for_status()

    print('Done')
