import io
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pandas as pd
from file_handler import FileHandler


def make_csv(content: str) -> bytes:
    return content.encode('utf-8')


def test_validate_good_csv():
    fh = FileHandler()
    csv = 'RRN,Amount,Date,RC,Tran_Type\n123,100,2025-12-01,00,U2\n'
    valid, err = fh.validate_file_bytes(make_csv(csv), 'good.csv')
    assert valid, f"Expected valid, got error: {err}"


def test_validate_missing_columns():
    fh = FileHandler()
    csv = 'id,amt,dt\n1,100,2025-12-01\n'
    valid, err = fh.validate_file_bytes(make_csv(csv), 'bad.csv')
    assert not valid
    assert 'Missing required columns' in err


def test_validate_tran_type_invalid():
    fh = FileHandler()
    csv = 'RRN,Amount,Date,RC,Tran_Type\n123,100,2025-12-01,00,X1\n'
    valid, err = fh.validate_file_bytes(make_csv(csv), 'bad2.csv')
    assert not valid
    assert 'Tran_Type' in err
