from services.annexure_iv import generate_annexure_iv_csv
import os

sample = [
    {
        'Bankadjref': 'BR-A-0001',
        'Flag': 'DRC',
        'shtdat': '2026-01-04',
        'adjsmt': '1234.50',
        'Shser': '518221608885',
        'Shcrd': 'NBIN1234567890',
        'FileName': 'cbs_inward_20260104.csv',
        'reason': '101',
        'specifyother': 'Auto-reversal'
    },
    {
        'Bankadjref': 'BR-A-0002',
        'Flag': 'RET',
        'shtdat': '2026-01-04',
        'adjsmt': '250.00',
        'Shser': '518221608846',
        'Shcrd': 'NBIN0987654321',
        'FileName': 'npci_inward_20260104.csv',
        'reason': '201',
        'specifyother': 'Remitter refund required'
    }
]

outp = os.path.join(os.path.dirname(__file__), '..', 'data', 'output', 'annexure_iv_generated.csv')
os.makedirs(os.path.dirname(outp), exist_ok=True)
generate_annexure_iv_csv(sample, outp)
print('Wrote sample to', outp)
