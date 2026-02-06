import os
import argparse
import json
import time
from datetime import datetime, timedelta

# Robust import for UPLOAD_DIR: try local `config`, then `backend.config`,
# then add parent folder to sys.path and retry.
try:
    from config import UPLOAD_DIR
except Exception:
    try:
        from backend.config import UPLOAD_DIR
    except Exception:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        try:
            from config import UPLOAD_DIR
        except Exception:
            raise


def iso(ts):
    return datetime.fromtimestamp(ts).isoformat()


def find_unstructured(upload_dir):
    """Return list of paths that don't conform to the new structured layout.

    New structured layouts are:
      uploads/{name}/Inward/...
      uploads/{name}/Outward/...
      uploads/{name}/Cycles/{CycleN}/{Inward|Outward}/...

    Legacy run folders are typically RUN_YYYYMMDD_xxx under UPLOAD_DIR.
    """
    unstructured = []
    for entry in os.listdir(upload_dir):
        path = os.path.join(upload_dir, entry)
        if not os.path.isdir(path):
            continue

        # If folder name starts with RUN_ treat as legacy run folder
        if entry.startswith('RUN_'):
            continue

        # If folder contains Inward or Outward or Cycles subfolders, it's structured
        children = os.listdir(path)
        low = [c.lower() for c in children]
        if any(c in low for c in ('inward', 'outward', 'cycles')):
            continue

        # otherwise mark as unstructured
        unstructured.append(path)

    return unstructured


def delete_old_runs(upload_dir, days, dry_run=True):
    cutoff = time.time() - days * 86400
    deleted = []
    candidates = []
    for entry in os.listdir(upload_dir):
        path = os.path.join(upload_dir, entry)
        if not os.path.isdir(path):
            continue
        # Only consider legacy run folders named RUN_
        if not entry.startswith('RUN_'):
            continue
        mtime = os.path.getmtime(path)
        if mtime < cutoff:
            candidates.append((path, mtime))

    for path, mtime in candidates:
        if dry_run:
            deleted.append({'path': path, 'mtime': iso(mtime), 'action': 'would-delete'})
        else:
            try:
                # safe delete: remove directory tree
                import shutil
                shutil.rmtree(path)
                deleted.append({'path': path, 'mtime': iso(mtime), 'action': 'deleted'})
            except Exception as e:
                deleted.append({'path': path, 'mtime': iso(mtime), 'action': f'error: {e}'})

    return deleted


def main():
    parser = argparse.ArgumentParser(description='Cleanup and report uploads directory')
    parser.add_argument('--days', type=int, default=30, help='Delete legacy runs older than this many days')
    parser.add_argument('--dry-run', action='store_true', default=False, help='Do not actually delete; only report')
    parser.add_argument('--report', type=str, default=None, help='Save JSON report to file')

    args = parser.parse_args()

    upload_dir = UPLOAD_DIR
    if not os.path.exists(upload_dir):
        print('UPLOAD_DIR does not exist:', upload_dir)
        return

    print('Scanning UPLOAD_DIR:', upload_dir)

    unstructured = find_unstructured(upload_dir)
    print(f'Found {len(unstructured)} unstructured top-level folders')

    old = delete_old_runs(upload_dir, args.days, dry_run=args.dry_run)
    print(f'Legacy RUN_ folders affected: {len(old)}')

    report = {
        'timestamp': datetime.utcnow().isoformat(),
        'upload_dir': upload_dir,
        'unstructured_count': len(unstructured),
        'unstructured': unstructured,
        'legacy_runs_affected': old,
        'dry_run': args.dry_run,
        'days_threshold': args.days
    }

    if args.report:
        try:
            with open(args.report, 'w') as f:
                json.dump(report, f, indent=2)
            print('Saved report to', args.report)
        except Exception as e:
            print('Could not write report:', e)

    else:
        print('--- Report ---')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
