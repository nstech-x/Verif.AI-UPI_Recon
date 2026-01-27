import pandas as pd
from pathlib import Path
p = Path(__file__).parents[1] / 'bank_recon_files' / 'Issuer_Raw_20260103.xlsx'
out = Path(__file__).parents[1] / 'bank_recon_files' / 'issuer_preview.txt'
if not p.exists():
    print('missing', p)
    raise SystemExit(2)
try:
    df = pd.read_excel(p, sheet_name=0, dtype=str)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('COLUMNS:\n')
        f.write('\n'.join(df.columns.astype(str).tolist()) + '\n\n')
        f.write('FIRST_50_ROWS:\n')
        f.write(df.head(50).to_string(index=False))
    print('OK', out)
except Exception as e:
    print('ERR', e)
    raise SystemExit(3)
