# Chatbot API Documentation

## Overview
The Chatbot API is a FastAPI-based service for transaction reconciliation lookups. It provides endpoints to query transaction details by RRN (Retrieval Reference Number) or Transaction ID across CBS, Switch, and NPCI systems.

## Base URL
```
http://localhost:8000
```

## Authentication
No authentication required (prototype).

## Endpoints

### 1. Root Endpoint 
**GET** `/`

Returns API information and available endpoints.

**Response:**
```json
{
  "service": "Transaction Chatbot API",
  "version": "1.0.0",
  "status": "running",
  "data_loaded": true,
  "endpoints": {
    "chatbot": "/api/v1/chatbot?rrn=636397811101708",
    "health": "/health",
    "stats": "/api/v1/stats",
    "reload": "/api/v1/reload (POST)",
    "docs": "/docs"
  }
}
```

### 2. Health Check
**GET** `/health`

Returns service health status and data availability.

**Response:**
```json
{
  "status": "healthy",
  "service": "chatbot-service",
  "version": "1.0.0",
  "data_loaded": true,
  "transaction_count": 150,
  "current_run_id": "RUN_20251125_001",
  "loaded_at": "2025-11-25T10:30:00Z"
}
```

### 3. Chatbot Lookup
**GET** `/api/v1/chatbot`

Main endpoint for transaction lookups.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `rrn` | string | Optional* | 12+ digit Retrieval Reference Number |
| `txn_id` | string | Optional* | Transaction ID (e.g., TXN001) |

*Note: At least one parameter must be provided.

**Success Response (200):**
```json
{
  "rrn": "123456789012",
  "txn_id": "TXN001",
  "amount": 5000.0,
  "date": "2025-11-25",
  "cbs": {
    "found": true,
    "amount": 5000.0,
    "date": "2025-11-25",
    "dr_cr": "Cr",
    "rc": "00"
  },
  "switch": {
    "found": true,
    "amount": 5000.0,
    "date": "2025-11-25",
    "tran_type": "UPI"
  },
  "npci": {
    "found": false
  },
  "status": "PARTIAL_MATCH",
  "direction": "INWARD",
  "recon_run_id": "RUN_20251125_001"
}
```

**Error Responses:**

**400 - Validation Error:**
```json
{
  "error": "Validation error",
  "message": "Invalid RRN format. RRN must be at least 12 digits",
  "details": {
    "provided": "12345",
    "expected_format": "12 or more digits (e.g., 636397811101708)",
    "length": 5
  }
}
```

**404 - Transaction Not Found:**
```json
{
  "error": "Transaction not found",
  "query": {
    "rrn": "999999999999"
  },
  "message": "No transaction found with RRN 999999999999 in reconciliation run RUN_20251125_001",
  "recon_run_id": "RUN_20251125_001",
  "suggestions": [
    "Check if the RRN is correct",
    "Try searching by transaction ID instead",
    "Verify the transaction was included in the latest reconciliation batch",
    "Contact support if this is a recent transaction"
  ]
}
```

**500 - Internal Server Error:**
```json
{
  "error": "Internal server error",
  "message": "Database connection failed",
  "context": "chatbot_lookup",
  "type": "ConnectionError"
}
```

### 4. Statistics
**GET** `/api/v1/stats`

Returns reconciliation data statistics.

**Response:**
```json
{
  "status": "loaded",
  "total_transactions": 150,
  "rrn_indexed": 150,
  "txn_indexed": 150,
  "status_breakdown": {
    "FULL_MATCH": 120,
    "PARTIAL_MATCH": 25,
    "NO_MATCH": 5
  },
  "current_run_id": "RUN_20251125_001",
  "loaded_at": "2025-11-25T10:30:00Z",
  "data_path": "./data/output"
}
```

### 5. Reload Data
**POST** `/api/v1/reload`

Reloads reconciliation data from the latest run.

**Response (Success):**
```json
{
  "status": "success",
  "message": "Data reloaded from RUN_20251125_002",
  "transaction_count": 180,
  "loaded_at": "2025-11-25T11:00:00Z"
}
```

**Response (No Change):**
```json
{
  "status": "no_change",
  "message": "Already using latest run: RUN_20251125_001",
  "transaction_count": 150
}
```

## Data Models

### Transaction Status
- `FULL_MATCH`: Transaction found in all three systems (CBS, Switch, NPCI)
- `PARTIAL_MATCH`: Transaction found in 1-2 systems
- `NO_MATCH`: Transaction not found in any system

### Transaction Direction
- `INWARD`: Money coming into the system
- `OUTWARD`: Money going out of the system

### System Fields

#### CBS (Core Banking System)
| Field | Type | Description |
|-------|------|-------------|
| `found` | boolean | Transaction exists in CBS |
| `amount` | float | Transaction amount |
| `date` | string | Transaction date (YYYY-MM-DD) |
| `dr_cr` | string | Debit/Credit indicator |
| `rc` | string | Response code |

#### Switch
| Field | Type | Description |
|-------|------|-------------|
| `found` | boolean | Transaction exists in Switch |
| `amount` | float | Transaction amount |
| `date` | string | Transaction date (YYYY-MM-DD) |
| `tran_type` | string | Transaction type (UPI, IMPS, etc.) |

#### NPCI (National Payments Corporation of India)
| Field | Type | Description |
|-------|------|-------------|
| `found` | boolean | Transaction exists in NPCI |
| `amount` | float | Transaction amount |
| `date` | string | Transaction date (YYYY-MM-DD) |

## Usage Examples

### Python with Requests
```python
import requests

# Lookup by RRN
response = requests.get(
    "http://localhost:8000/api/v1/chatbot",
    params={"rrn": "123456789012"}
)
print(response.json())

# Lookup by Transaction ID
response = requests.get(
    "http://localhost:8000/api/v1/chatbot",
    params={"txn_id": "TXN001"}
)
print(response.json())
```

### cURL Examples
```bash
# Health check
curl http://localhost:8000/health

# Lookup by RRN
curl "http://localhost:8000/api/v1/chatbot?rrn=123456789012"

# Lookup by Transaction ID
curl "http://localhost:8000/api/v1/chatbot?txn_id=TXN001"

# Get statistics
curl http://localhost:8000/api/v1/stats
```

## Performance
- **Response Time**: < 500ms for single transaction lookup
- **Throughput**: Supports multiple concurrent requests
- **Indexing**: O(1) lookup using in-memory indexes

## Error Handling
- All endpoints return appropriate HTTP status codes
- Error responses include detailed messages and suggestions
- Validation errors provide specific guidance for correction

## Rate Limiting
No rate limiting implemented (prototype).

## Versioning
API version is included in the URL path (`/api/v1/`).

## Changelog
- **v1.0.0**: Initial release with basic lookup functionality

## Support
For issues or questions:
- **Developer**: Ankit
- **Component**: Transaction Lookup Service
- **Contact**: 
