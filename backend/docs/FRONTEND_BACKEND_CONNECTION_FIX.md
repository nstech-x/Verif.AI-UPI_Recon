# Frontend-Backend Connection Fix

## Issues Fixed

### 1. **Endpoint Path Handling**
**Problem**: Frontend requests nested paths like `/api/v1/reports/recon/gl_vs_switch/matched/inward` but FastAPI wasn't capturing the full path.

**Solution**: Changed endpoint from `@app.get("/api/v1/reports/{report_type}")` to `@app.get("/api/v1/reports/{report_type:path}")` to capture nested paths.

**Files Modified**:
- `backend/app.py` (line 1437)

### 2. **TTUM File Corruption**
**Problem**: TTUM CSV files were truncated mid-line, causing corruption when downloaded.

**Root Cause**: Files weren't being properly flushed to disk before closing.

**Solution**: Added explicit `f.flush()` and `os.fsync(f.fileno())` calls after writing CSV data.

**Files Modified**:
- `backend/reporting.py` - `write_ttum_csv()` and `write_report()` functions

### 3. **Missing Report Mappings**
**Problem**: Frontend requested reports that weren't mapped in the backend endpoint.

**Solution**: Added comprehensive report mapping including:
- `ttum` → `['ttum_candidates']`
- Alternative patterns for all report types
- Fallback pattern generation from path

## Frontend Report Endpoints

### Working Endpoints
All these endpoints now return the correct files:

#### Listing Reports
- `/api/v1/reports/cbs_beneficiary` → cbs_beneficiary/cbs_inward files
- `/api/v1/reports/cbs_remitter` → cbs_remitter/cbs_outward files
- `/api/v1/reports/switch_inward` → switch_inward files
- `/api/v1/reports/switch_outward` → switch_outward files
- `/api/v1/reports/npci_inward` → npci_inward files
- `/api/v1/reports/npci_outward` → npci_outward files

#### Reconciliation Reports (Pairwise Matched)
- `/api/v1/reports/recon/gl_vs_switch/matched/inward` → GL_vs_Switch_Inward.csv
- `/api/v1/reports/recon/gl_vs_switch/matched/outward` → GL_vs_Switch_Outward.csv
- `/api/v1/reports/recon/switch_vs_network/matched/inward` → Switch_vs_NPCI_Inward.csv
- `/api/v1/reports/recon/switch_vs_network/matched/outward` → Switch_vs_NPCI_Outward.csv
- `/api/v1/reports/recon/gl_vs_network/matched/inward` → GL_vs_NPCI_Inward.csv
- `/api/v1/reports/recon/gl_vs_network/matched/outward` → GL_vs_NPCI_Outward.csv

#### Ageing Reports (Unmatched)
- `/api/v1/reports/recon/gl_vs_switch/unmatched/inward` → Unmatched_Inward_Ageing.csv
- `/api/v1/reports/recon/gl_vs_switch/unmatched/outward` → Unmatched_Outward_Ageing.csv
- `/api/v1/reports/recon/switch_vs_network/unmatched/inward` → Unmatched_Inward_Ageing.csv
- `/api/v1/reports/recon/switch_vs_network/unmatched/outward` → Unmatched_Outward_Ageing.csv
- `/api/v1/reports/recon/gl_vs_network/unmatched/inward` → Unmatched_Inward_Ageing.csv
- `/api/v1/reports/recon/gl_vs_network/unmatched/outward` → Unmatched_Outward_Ageing.csv

#### Hanging Transaction Reports
- `/api/v1/reports/recon/hanging_transactions/inward` → Hanging_Inward.csv
- `/api/v1/reports/recon/hanging_transactions/outward` → Hanging_Outward.csv

#### TTUM Reports
- `/api/v1/reports/ttum` → ttum_candidates.csv/xlsx
- `/api/v1/reports/ttum/csv` → ttum_candidates.csv (ZIP if multiple)
- `/api/v1/reports/ttum/xlsx` → ttum_candidates.xlsx (ZIP if multiple)

#### Annexure Reports
- `/api/v1/reports/annexure/i/raw` → ANNEXURE_I files
- `/api/v1/reports/annexure/ii/raw` → ANNEXURE_II files
- `/api/v1/reports/annexure/iii/adjustment` → ANNEXURE_III/IV files
- `/api/v1/reports/annexure/iv/bulk` → ANNEXURE_IV files

#### Bulk Downloads
- `/api/v1/reports/matched` → ZIP of all pairwise matched reports
- `/api/v1/reports/matched/csv` → matched_transactions.csv
- `/api/v1/reports/unmatched` → JSON array of unmatched exceptions
- `/api/v1/reports/unmatched/csv` → unmatched_exceptions.csv
- `/api/v1/reports/summary` → Summary JSON
- `/api/v1/reports/all` → ZIP of all reports

## Generated Reports

After reconciliation, the following reports are generated in `OUTPUT_DIR/<RUN_ID>/reports/`:

### Core Reports (Always Generated)
1. **unmatched_exceptions.csv** - All unmatched transactions with exception details
2. **unmatched_exceptions.xlsx** - Excel version of unmatched exceptions
3. **ttum_candidates.csv** - Transactions requiring TTUM entries
4. **ttum_candidates.xlsx** - Excel version of TTUM candidates

### Pairwise Matched Reports (6 files)
5. **GL_vs_Switch_Inward.csv** - CBS-Switch matched inward transactions
6. **GL_vs_Switch_Outward.csv** - CBS-Switch matched outward transactions
7. **Switch_vs_NPCI_Inward.csv** - Switch-NPCI matched inward transactions
8. **Switch_vs_NPCI_Outward.csv** - Switch-NPCI matched outward transactions
9. **GL_vs_NPCI_Inward.csv** - CBS-NPCI matched inward transactions
10. **GL_vs_NPCI_Outward.csv** - CBS-NPCI matched outward transactions

### Ageing Reports (2 files)
11. **Unmatched_Inward_Ageing.csv** - Inward unmatched with age buckets (0-1, 2-3, >3 days)
12. **Unmatched_Outward_Ageing.csv** - Outward unmatched with age buckets

### Hanging Transaction Reports (2 files - if applicable)
13. **Hanging_Inward.csv** - Inward hanging transactions
14. **Hanging_Outward.csv** - Outward hanging transactions

## Testing

### Test the Fix
1. Start the backend server:
   ```bash
   cd backend
   uvicorn app:app --reload
   ```

2. Test a specific endpoint:
   ```bash
   curl http://localhost:8000/api/v1/reports/recon/gl_vs_switch/matched/inward
   ```

3. Check frontend downloads work by clicking download buttons in the UI

### Verify TTUM Files
```bash
# Check file is complete (should have 81 lines for current data)
powershell -Command "Get-Content 'data/output/RUN_20260107_123336/reports/ttum_candidates.csv' | Measure-Object -Line"

# Check last few lines are complete
powershell -Command "Get-Content 'data/output/RUN_20260107_123336/reports/ttum_candidates.csv' -Tail 3"
```

## Regenerating Reports for Existing Runs

If you have existing reconciliation runs with missing/corrupted reports:

```bash
cd backend
python regenerate_reports.py RUN_20260107_123336
```

Or regenerate for the latest run:
```bash
python regenerate_reports.py
```

## Key Changes Summary

| File | Change | Purpose |
|------|--------|---------|
| `app.py` | Changed `{report_type}` to `{report_type:path}` | Capture nested URL paths |
| `app.py` | Added `ttum` mapping | Map `/api/v1/reports/ttum` to ttum_candidates files |
| `reporting.py` | Added `f.flush()` and `os.fsync()` | Ensure files are completely written |
| `regenerate_reports.py` | Removed Unicode emojis | Fix Windows console encoding errors |

## Notes

- All reports are generated during reconciliation in `generate_upi_report()` method
- Reports are stored in `OUTPUT_DIR/<RUN_ID>/reports/`
- TTUM files are also copied to `OUTPUT_DIR/<RUN_ID>/ttum/` for backward compatibility
- File corruption was caused by Python's buffered I/O not flushing before process termination
- The `:path` parameter in FastAPI captures the entire remaining path including slashes
