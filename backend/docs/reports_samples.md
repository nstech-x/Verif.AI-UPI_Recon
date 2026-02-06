Below are sample output rows (CSV) for each generated report type. These are examples only — actual files are UTF-8 CSVs generated per run and saved under `reports/`.

1) GL_vs_Switch_Inward.csv (columns: run_id,generated_at,RRN,Amount,Date,Tran_Type,RC,Source_Systems)
RUN_20260104_000000,2026-01-04T12:00:00,518221608885,150.00,2026-01-04,U2,00,CBS/SWITCH

2) GL_vs_Switch_Outward.csv
RUN_20260104_000000,2026-01-04T12:00:00,518221608886,200.50,2026-01-04,U3,00,CBS/SWITCH

3) Switch_vs_NPCI_Inward.csv
RUN_20260104_000000,2026-01-04T12:00:00,518221608887,100.00,2026-01-04,U2,00,SWITCH/NPCI

4) Switch_vs_NPCI_Outward.csv
RUN_20260104_000000,2026-01-04T12:00:00,518221608888,75.25,2026-01-04,U3,00,SWITCH/NPCI

5) GL_vs_NPCI_Inward.csv
RUN_20260104_000000,2026-01-04T12:00:00,518221608889,500.00,2026-01-04,U2,00,CBS/NPCI

6) GL_vs_NPCI_Outward.csv
RUN_20260104_000000,2026-01-04T12:00:00,518221608890,250.00,2026-01-04,U3,00,CBS/NPCI

7) Unmatched_Inward_Ageing.csv (columns: run_id,generated_at,RRN,Present_Systems,Missing_Systems,Ageing_Bucket,Ageing_Days,Amount,Date,Source_Systems)
RUN_20260104_000000,2026-01-04T12:00:00,518221608891,CBS/SWITCH,NPCI,2-3 days,2,120.00,2026-01-02,CBS/SWITCH

8) Unmatched_Outward_Ageing.csv
RUN_20260104_000000,2026-01-04T12:00:00,518221608892,SWITCH,NPCI/CBS,>3 days,5,80.00,2025-12-30,SWITCH

9) Hanging_Transactions_Inward.csv (columns: run_id,generated_at,RRN,Amount,Date,Reason,Present_Systems,Missing_Systems,Source_Systems)
RUN_20260104_000000,2026-01-04T12:00:00,518221608893,300.00,2026-01-04,declined_with_reversal,CBS/SWITCH,NPCI,CBS/SWITCH

10) Hanging_Transactions_Outward.csv
RUN_20260104_000000,2026-01-04T12:00:00,518221608894,50.00,2026-01-04,declined_with_reversal,SWITCH,NPCI/CBS,SWITCH

11) TTUM CSVs: placed under run_folder/ttum/*.csv with rows like:
InstructionType,InstructionRefNo,RRN,Amount,ValueDate,DrCr,RC,Tran_Type,AccountNo,IFSC,Narration,TTUM_Code,GL_Debit_Account,GL_Credit_Account
DRC,TTUM_DRC_518221608895,518221608895,100.00,20260104,D,12,U2,,,DRC for 518221608895,DRC,200100,100200

12) ANNEXURE_IV_<run_id>.csv: strict columns: Bankadjref,Flag,shtdat,adjsmt,Shser,Shcrd,FileName,reason,specifyother
BR_TCC_518221608885, TCC,2026-01-04,150.00,518221608885,NBIN518221608885,ANNEXURE_RUN_20260104_000000.csv,100,Auto-reversal detected

13) Switch_Update_File.csv (columns: run_id,generated_at,RRN,Old_Status,New_Status,Reason,Date,Source_Systems)
RUN_20260104_000000,2026-01-04T12:00:00,518221608885,02,MATCHED,TCC_103,2026-01-04,CBS/SWITCH/NPCI


Note: These are sample rows for illustration. Real outputs include `run_id` and `generated_at` on every row for audit/traceability.
