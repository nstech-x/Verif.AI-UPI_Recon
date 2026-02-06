# API Documentation

## NSTechX Bank Reconciliation API

### Overview
This API provides bank reconciliation services for CBS, Switch, and NPCI transaction matching. It accepts Excel/CSV files, performs reconciliation, and provides outputs for UI and chatbot integration.

### Base URL
```
http://localhost:8000
```

### Authentication
No authentication required (Prototype system)

---

## API Endpoints

### 1. File Upload
**Endpoint:** `POST /api/v1/upload`

**Description:** Upload 7 reconciliation files (3 mandatory, 4 optional)

**Request Format:** `multipart/form-data`

**Required Files:**
- `cbs_inward` - CBS inward transactions
- `switch` - Switch transactions  
- `npci_inward` - NPCI inward transactions
- `cbs_outward` - CBS outward transactions (optional)
- `npci_outward` - NPCI outward transactions (optional)
- `ntsl` - NTSL data (optional)
- `adjustment` - Adjustment data (optional)

**Request Example:**
```javascript
// Using FormData
const formData = new FormData();
formData.append('cbs_inward', cbsFile);
formData.append('switch', switchFile);
formData.append('npci_inward', npciFile);
formData.append('cbs_outward', dummyFile);
formData.append('npci_outward', dummyFile);
formData.append('ntsl', dummyFile);
formData.append('adjustment', dummyFile);

fetch('http://localhost:8000/api/v1/upload', {
  method: 'POST',
  body: formData
})
```

**Response:**
```json
{
  "status": "success",
  "message": "Files uploaded successfully",
  "run_id": "RUN_20251128_153045",
  "folder": "data/uploads/RUN_20251128_153045"
}
```

---

### 2. Run Reconciliation
**Endpoint:** `POST /api/v1/recon/run`

**Description:** Trigger reconciliation process on uploaded files

**Request Body:** (Optional)
```json
{
  "direction": "INWARD"  // Default: "INWARD"
}
```

**Request Example:**
```javascript
fetch('http://localhost:8000/api/v1/recon/run', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ direction: "INWARD" })
})
```

**Response:**
```json
{
  "status": "completed",
  "run_id": "RUN_20251128_153045",
  "output_folder": "data/output/RUN_20251128_153045",
  "matched_count": 5,
  "unmatched_count": 0,
  "exception_count": 0,
  "partial_match_count": 0,
  "orphan_count": 0
}
```

---

### 3. Get Reconciliation Report
**Endpoint:** `GET /api/v1/recon/latest/report`

**Description:** Get the latest reconciliation summary report

**Request Example:**
```javascript
fetch('http://localhost:8000/api/v1/recon/latest/report')
  .then(response => response.text())
  .then(data => console.log(data));
```

**Response:** Plain text report content

---

### 4. Get Adjustments CSV
**Endpoint:** `GET /api/v1/recon/latest/adjustments`

**Description:** Get CSV file for Force Match UI with reconciliation exceptions

**Request Example:**
```javascript
fetch('http://localhost:8000/api/v1/recon/latest/adjustments')
  .then(response => response.blob())
  .then(blob => {
    // Create download link
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'adjustments.csv';
    a.click();
  });
```

**Response:** CSV file download

---

### 5. Get Raw Reconciliation Data
**Endpoint:** `GET /api/v1/recon/latest/raw`

**Description:** Get raw reconciliation data for chatbot integration (RRN-centric)

**Request Example:**
```javascript
fetch('http://localhost:8000/api/v1/recon/latest/raw')
  .then(response => response.json())
  .then(data => {
    console.log('Run ID:', data.run_id);
    console.log('Total RRNs:', data.summary.total_rrns);
    console.log('Data:', data.data);
  });
```

**Response:**
```json
{
  "run_id": "RUN_20251128_153045",
  "data": {
    "355481530062": {
      "cbs": {
        "amount": 8531.27,
        "date": "2025-11-26",
        "dr_cr": "Cr",
        "rc": "0",
        "tran_type": "UPI"
      },
      "switch": {
        "amount": 8531.27,
        "date": "2025-11-26"
      },
      "npci": {
        "amount": 8531.27,
        "date": "2025-11-26"
      },
      "status": "MATCHED"
    }
  },
  "summary": {
    "total_rrns": 5,
    "matched_count": 5,
    "unmatched_count": 0,
    "exception_count": 0,
    "file_path": "data/output/RUN_20251128_153045/recon_output.json"
  }
}
```

---

### 6. Force Match API
**Endpoint:** `POST /api/v1/force-match`

**Description:** Force match two RRNs from different systems (NSTechX Screen 013-014)

**Request Parameters:**
- `rrn` (query) - RRN to force match
- `source1` (query) - First source system (cbs/switch/npci)
- `source2` (query) - Second source system (cbs/switch/npci)
- `action` (query) - Action type (default: "match")

**Request Example:**
```javascript
fetch('http://localhost:8000/api/v1/force-match?rrn=355481530062&source1=cbs&source2=switch&action=match', {
  method: 'POST'
})
```

**Response:**
```json
{
  "status": "success",
  "message": "RRN 355481530062 force matched between cbs and switch",
  "action": "match",
  "rrn": "355481530062"
}
```

---

### 7. Chatbot / Enquiry API
**Endpoint (path):** `GET /api/v1/chatbot/{rrn}`
**Endpoint (query):** `GET /api/v1/chatbot?rrn=355481530062` or `GET /api/v1/chatbot?txn_id=001`

**Description:** Search for specific RRN details or transaction by transaction id (replaces the previous `enquiry` route). Path-based lookup keeps the original behaviour and returns identical payloads.

**Path Parameter:**
- `rrn` - RRN to search for

**Request Examples:**
```javascript
// Path-based (backwards compatible with older clients)
fetch('http://localhost:8000/api/v1/chatbot/355481530062')
  .then(response => response.json())
  .then(data => console.log(data));

// Query-based (supports txn_id lookups too)
fetch('http://localhost:8000/api/v1/chatbot?txn_id=001')
  .then(response => response.json())
  .then(data => console.log(data));
```

**Response (example):**
```json
{
  "rrn": "355481530062",
  "details": {
    "cbs": {
      "amount": 8531.27,
      "date": "2025-11-26",
      "dr_cr": "Cr",
      "rc": "0",
      "tran_type": "UPI"
    },
    "switch": {
      "amount": 8531.27,
      "date": "2025-11-26"
    },
    "npci": {
      "amount": 8531.27,
      "date": "2025-11-26"
    },
    "status": "MATCHED"
  },
  "run_id": "RUN_20251128_153045"
}
```

---

### 8. Auto-Match Parameters API
**Endpoint:** `POST /api/v1/auto-match/parameters`

**Description:** Set auto-match parameters (NSTechX Screen 015)

**Request Parameters:**
- `amount_tolerance` (query) - Amount tolerance for matching (default: 0.0)
- `date_tolerance_days` (query) - Date tolerance in days (default: 0)
- `enable_auto_match` (query) - Enable auto-matching (default: true)

**Request Example:**
```javascript
fetch('http://localhost:8000/api/v1/auto-match/parameters?amount_tolerance=1.0&date_tolerance_days=1&enable_auto_match=true', {
  method: 'POST'
})
```

**Response:**
```json
{
  "status": "success",
  "parameters": {
    "amount_tolerance": 1.0,
    "date_tolerance_days": 1,
    "enable_auto_match": true
  }
}
```

---

### 9. Reports API
**Endpoint:** `GET /api/v1/reports/{report_type}`

**Description:** Generate different types of reports (NSTechX Screen 018-019)

**Path Parameter:**
- `report_type` - Type of report (matched/unmatched/summary/ttum)

**Request Example:**
```javascript
fetch('http://localhost:8000/api/v1/reports/matched')
  .then(response => response.json())
  .then(data => console.log(data));
```

**Response Examples:**
- **Matched Report:**
```json
{
  "report_type": "matched",
  "data": {
    "355481530062": { ... }
  },
  "count": 5
}
```

- **Unmatched Report:**
```json
{
  "report_type": "unmatched",
  "data": {
    "455500006551": { ... }
  },
  "count": 4
}
```

- **Summary Report:**
```json
{
  "report_type": "summary",
  "data": {
    "total_transactions": 9,
    "matched": 5,
    "partial_match": 0,
    "orphan": 4,
    "mismatch": 0,
    "unmatched": 4
  }
}
```

---

### 10. Rollback API
**Endpoint:** `POST /api/v1/rollback`

**Description:** Rollback reconciliation process (NSTechX Screen 016)

**Request Parameters:**
- `run_id` (query) - Specific run ID to rollback (optional, defaults to latest)

**Request Example:**
```javascript
fetch('http://localhost:8000/api/v1/rollback', {
  method: 'POST'
})
```

**Response:**
```json
{
  "status": "success",
  "message": "Reconciliation run RUN_20251128_153045 rolled back successfully"
}
```

---

### 11. Summary API
**Endpoint:** `GET /api/v1/summary`

**Description:** Get reconciliation summary for dashboard (NSTechX Screen 010-011)

**Request Example:**
```javascript
fetch('http://localhost:8000/api/v1/summary')
  .then(response => response.json())
  .then(data => console.log(data));
```

**Response:**
```json
{
  "total_transactions": 5,
  "matched": 5,
  "unmatched": 0,
  "adjustments": 0,
  "status": "completed",
  "run_id": "RUN_20251128_153045"
}
```

---

### 12. Health Check
**Endpoint:** `GET /health`

**Description:** Check API health status

**Request Example:**
```javascript
fetch('http://localhost:8000/health')
  .then(response => response.json())
  .then(data => console.log(data));
```

**Response:**
```json
{
  "status": "healthy",
  "service": "NSTechX Reconciliation API"
}
```

---

## Frontend Integration Guide

### Prerequisites
1. **Backend Server Running**
   - Ensure backend is running on `http://localhost:8000`
   - Test with: `curl http://localhost:8000/health`

2. **CORS Configuration** (if needed)
   - Backend should handle CORS automatically
   - If issues occur, check backend CORS settings

3. **File Size Limitations**
   - Default FastAPI limit: 100MB per file
   - Excel files can be large - monitor upload times

### Integration Steps

#### Step 1: File Upload Integration
```javascript
// 1. Create file upload handler
const handleFileUpload = async (files) => {
  const formData = new FormData();
  
  // Add your 3 main files
  formData.append('cbs_inward', files.cbs);
  formData.append('switch', files.switch);
  formData.append('npci_inward', files.npci);
  
  // Add dummy files for the other 4
  const dummyFile = new File(["RRN,Amount,Tran_Date,Dr_Cr,RC,Tran_Type\n111111111111,0.0,2025-01-01,Cr,00,DUMMY"], "dummy.csv");
  formData.append('cbs_outward', dummyFile);
  formData.append('npci_outward', dummyFile);
  formData.append('ntsl', dummyFile);
  formData.append('adjustment', dummyFile);
  
  try {
    const response = await fetch('http://localhost:8000/api/v1/upload', {
      method: 'POST',
      body: formData
    });
    
    if (response.ok) {
      const data = await response.json();
      console.log('Upload successful:', data);
      return data;
    } else {
      throw new Error('Upload failed');
    }
  } catch (error) {
    console.error('Upload error:', error);
    throw error;
  }
};
```

#### Step 2: Reconciliation Process
```javascript
// 2. Run reconciliation after upload
const runReconciliation = async () => {
  try {
    const response = await fetch('http://localhost:8000/api/v1/recon/run', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ direction: "INWARD" })
    });
    
    if (response.ok) {
      const data = await response.json();
      console.log('Reconciliation completed:', data);
      return data;
    } else {
      throw new Error('Reconciliation failed');
    }
  } catch (error) {
    console.error('Reconciliation error:', error);
    throw error;
  }
};
```

#### Step 3: Display Results
```javascript
// 3. Get and display reconciliation results
const displayResults = async () => {
  try {
    // Get raw data for detailed view
    const rawResponse = await fetch('http://localhost:8000/api/v1/recon/latest/raw');
    const rawData = await rawResponse.json();
    
    // Get report for summary
    const reportResponse = await fetch('http://localhost:8000/api/v1/recon/latest/report');
    const reportText = await reportResponse.text();
    
    // Get CSV for force match
    const csvResponse = await fetch('http://localhost:8000/api/v1/recon/latest/adjustments');
    const csvBlob = await csvResponse.blob();
    
    return {
      rawData,
      reportText,
      csvBlob
    };
  } catch (error) {
    console.error('Results error:', error);
    throw error;
  }
};
```

### Error Handling
```javascript
// Common error handling
const handleApiError = (error) => {
  if (error.message.includes('Upload failed')) {
    alert('File upload failed. Please check file format and size.');
  } else if (error.message.includes('Reconciliation failed')) {
    alert('Reconciliation process failed. Please check file data.');
  } else {
    alert('An error occurred: ' + error.message);
  }
};
```

### UI Integration Points

#### File Upload Screen (Screens 005-007)
- Use `POST /api/v1/upload`
- Show progress during upload
- Validate file types (.xls, .xlsx, .csv)

#### Run Reconciliation Button (Screen 010)
- Use `POST /api/v1/recon/run`
- Show loading state during processing
- Display success/error messages

#### Results Dashboard (Screens 010-011)
- Use `GET /api/v1/summary` for dashboard counts
- Use `GET /api/v1/recon/latest/raw` for detailed data
- Use `GET /api/v1/recon/latest/report` for summary

#### Unmatched Dashboard (Screen 012)
- Use `GET /api/v1/reports/unmatched` for unmatched transactions
- Show toggle tabs for different sources

#### Force Match (Screens 013-014)
- Use `POST /api/v1/force-match` for manual matching
- Use `GET /api/v1/reports/unmatched` for force match list

#### Auto-Match Parameters (Screen 015)
- Use `POST /api/v1/auto-match/parameters` for auto-match settings

#### Rollback (Screen 016)
- Use `POST /api/v1/rollback` for rollback functionality

#### Chatbot / Enquiry (Screen 017)
- Use `GET /api/v1/chatbot/{rrn}` or `GET /api/v1/chatbot?txn_id=...` for lookups
- Show transaction status across all systems

#### Reports (Screens 018-019)
- Use `GET /api/v1/reports/{type}` for different report types
- Generate TTUM, NTSL, Settlement reports

### Testing Checklist
- [ ] File upload works with Excel files
- [ ] Reconciliation runs without errors
- [ ] All 12 endpoints return data
- [ ] CSV download works
- [ ] Report text displays correctly
- [ ] Raw data contains RRN information
- [ ] Force match updates RRN status
- [ ] Enquiry returns specific RRN details
- [ ] Rollback deletes output data
- [ ] Error states are handled gracefully

### Production Considerations
- Add authentication/authorization
- Implement file size validation
- Add progress tracking for large files
- Add database integration
- Add audit logging
- Add rate limiting
- Add maker-checker process for force match
- Add file rollback functionality

---

## Support
For API issues, contact the backend team or check the server logs.
