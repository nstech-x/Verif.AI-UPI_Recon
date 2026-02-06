import os
import re
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_OUTPUT = BASE_DIR / 'data' / 'output'


def find_latest_run(folder: Path):
    runs = [p for p in folder.iterdir() if p.is_dir() and p.name.startswith('RUN_')]
    if not runs:
        return None
    runs.sort()
    return runs[-1]


def move_file_into_run(file_name: str, run_folder: Path):
    src = DATA_OUTPUT / file_name
    if not src.exists():
        print(f"- {file_name} not found in {DATA_OUTPUT}")
        return
    dest = run_folder / file_name
    if dest.exists():
        print(f"- {file_name} already present in {run_folder}")
        return
    src.replace(dest)
    print(f"Moved {src} -> {dest}")


def normalize_recon_keys(run_folder: Path):
    recon_path = run_folder / 'recon_output.json'
    if not recon_path.exists():
        print(f"No recon_output.json in {run_folder}")
        return

    with open(recon_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, dict):
        print("recon_output.json is not a dict, skipping normalization")
        return

    changed = False
    new_data = {}
    float_key_re = re.compile(r'^(\d+)\.0$')

    for k, v in data.items():
        m = float_key_re.match(k)
        if m:
            new_key = m.group(1)
            if new_key in new_data:
                # If duplicate after normalization, prefer existing and skip
                print(f"Warning: duplicate key after normalization: {new_key} (skipping)")
                continue
            new_data[new_key] = v
            changed = True
        else:
            new_data[k] = v

    if changed:
        # Also attempt to fix txn_id fields inside transactions if they were stored as numeric strings with .0
        for rrn, txn in new_data.items():
            if isinstance(txn, dict):
                for field in ('txn_id', 'TXN_ID'):
                    val = txn.get(field)
                    if isinstance(val, str) and val.endswith('.0') and val.replace('.0', '').isdigit():
                        txn[field] = val.replace('.0', '')

        with open(recon_path, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, indent=2, ensure_ascii=False)
        print(f"Normalized recon keys in {recon_path}")
    else:
        print("No keys needed normalization")


def main():
    if not DATA_OUTPUT.exists():
        print(f"Output directory not found: {DATA_OUTPUT}")
        return

    latest_run = find_latest_run(DATA_OUTPUT)
    if latest_run is None:
        print("No RUN_* folders found in output directory")
        return

    print(f"Latest run: {latest_run.name}")

    # Move report and adjustments into run folder
    move_file_into_run('report.txt', latest_run)
    move_file_into_run('adjustments.csv', latest_run)

    # Normalize recon_output.json keys
    normalize_recon_keys(latest_run)


if __name__ == '__main__':
    main()
