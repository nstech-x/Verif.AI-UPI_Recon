import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engines.settlement_engine import SettlementEngine
se = SettlementEngine(output_dir='data/output')
ma = se.issuer_actions
print('mapped_count=', len(ma))
import itertools
for k,v in itertools.islice(ma.items(), 10):
    print(k, v)
