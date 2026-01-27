import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pandas as pd
from recon_engine import ReconciliationEngine


def test_reconcile_simple_match(tmp_path):
    df1 = pd.DataFrame({'RRN':['A1'], 'Amount':[100], 'Tran_Date':['2025-12-01'], 'Source':['CBS'], 'Dr_Cr':['D'], 'RC':['00'], 'Tran_Type':['U2']})
    df2 = pd.DataFrame({'RRN':['A1'], 'Amount':[100], 'Tran_Date':['2025-12-01'], 'Source':['SWITCH'], 'Dr_Cr':['C'], 'RC':['00'], 'Tran_Type':['U2']})
    df3 = pd.DataFrame({'RRN':['A1'], 'Amount':[100], 'Tran_Date':['2025-12-01'], 'Source':['NPCI'], 'Dr_Cr':['C'], 'RC':['00'], 'Tran_Type':['U2']})

    engine = ReconciliationEngine()
    results = engine.reconcile([df1, df2, df3])
    assert 'A1' in results
    assert results['A1']['status'] == 'MATCHED'

