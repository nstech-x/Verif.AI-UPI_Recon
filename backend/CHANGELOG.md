# Backend Changelog

This file tracks all the changes and new features implemented in the backend to meet the project requirements.

## Feature Implementation Checklist

- [ ] **API Endpoints**
    - [ ] Separate file upload (`/api/v1/upload`) from recon initiation.
    - [x] Separate file upload (`/api/v1/upload`) from recon initiation.  
    - [x] Implement `POST /api/v1/recon/run` to trigger a reconciliation cycle.  
    - [x] Implement `GET /api/v1/recon/latest/summary` for dashboard stats.  
    - [x] Implement `GET /api/v1/recon/latest/unmatched` to fetch unmatched transactions.  
    - [x] Implement `GET /api/v1/recon/latest/hanging` to fetch hanging transactions.  
    - [x] Implement `GET /api/v1/reports/ttum` to download TTUM files.  
    - [x] Implement `GET /api/v1/enquiry` for chatbot/RRN lookup.  

- [ ] **Core Reconciliation Logic (`recon_engine.py`)**
    - [ ] Add Cut-off Handling for cross-cycle reversals.
    - [x] Add Cut-off Handling for cross-cycle reversals. (declined-with-reversal detection implemented)
    - [x] Add Self-Reversal Matching (debit + credit with same RRN).
    - [x] Add NTSL Settlement Matching logic. (NTSL vs GL amount matching implemented)
    - [x] Add Duplicate Transaction Detection.
    - [x] Add TCC 102/103 Flagging for specific inward transactions.
    - [x] Add Failed Transaction Handling (NPCI fail + CBS success).
    - [x] Add Hanging Transaction Logic (wait 2 cycles).

- [ ] **Exception & TTUM Handling**
    - [x] Create a new module for generating TTUM files. (`settlement_engine.generate_ttum_files`)  
    - [x] Implement logic to identify exceptions that require a TTUM. (flags and heuristics present)  
    - [x] Generate TTUM files in the required NPCI bulk upload format. (TTUM CSVs produced with Annexure-IV-like headers and GL account mapping columns; validate against NPCI Annexure IV spec)

- [ ] **Reporting**
    - [x] Generate individual Matched Reports (CSV).  
    - [x] Generate Unmatched Report with ageing analysis (CSV).  
    - [x] Generate Hanging Transactions Report (CSV).  
    - [x] Generate a consolidated GL Statement (CSV).

- [ ] **Audit & Rollback**
    - [x] Integrate `audit_trail.py` into key application events (upload, recon, rollback).
    - [x] Integrate `rollback_manager.py` to be triggered via an API endpoint.
    - [x] Add `POST /api/v1/recon/rollback` endpoint.

- [ ] **Authentication**
    - [x] Add user role verification to critical endpoints. (JWT auth + `get_current_user` dependency applied)
