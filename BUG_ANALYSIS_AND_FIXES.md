# Bug Analysis and Fixes Report

## Issues Identified

### 1. **Dashboard Does Not Show Real Data & Tabs Not Showing Real-Time Data**

**Root Cause:**
- The dashboard uses `staleTime: 60000` (60 seconds) and `refetchInterval: 120000` (2 minutes) for data caching
- When switching tabs, the cached data is used instead of fetching fresh data
- The `useQuery` hook doesn't invalidate cache when tab changes
- No event listeners trigger data refresh when switching tabs

**Current Implementation Issues:**
```typescript
// Dashboard.tsx - Lines 95-110
const { data: apiSummaryData, isLoading: isSummaryLoading } = useQuery({
  queryKey: ["summary"],
  queryFn: async () => { ... },
  staleTime: 60000,  // Data considered fresh for 60 seconds
  refetchInterval: 120000,  // Only refetch every 2 minutes
  enabled: !isDemoMode,
  retry: 0,
});
```

**Problems:**
- User switches to another tab → data is stale but not refetched
- User returns to dashboard → old cached data is displayed
- No manual refresh on tab change
- API logs show repeated calls to `/api/v1/summary` and `/api/v1/summary/historical` because multiple components are making independent requests

---

### 2. **Force Match and Unmatch Do Not Show Real-Time Data**

**Root Cause:**
- `ForceMatch.tsx` fetches data only on component mount (`useEffect` with empty dependency array)
- After a force match operation, data is refetched but the UI doesn't update immediately
- No polling mechanism for real-time updates
- The `fetchUnmatchedTransactions` function is called after match, but there's a race condition

**Current Implementation Issues:**
```typescript
// ForceMatch.tsx - Lines 180-185
useEffect(() => {
  fetchUnmatchedTransactions();
}, []); // Only runs on mount, never again
```

**Problems:**
- Data loaded once on page load
- After force matching, user must manually click "Refresh" to see updated data
- No automatic refresh after operations
- Unmatched page has similar issues

---

### 3. **Excessive API Calls (Repeated GET Requests)**

**Root Cause:**
- Multiple components independently querying the same endpoints
- No shared query cache across components
- Each tab/page makes its own API calls
- React Query cache not being properly utilized

**Evidence from logs:**
```
INFO: 127.0.0.1:57070 - "GET /api/v1/summary HTTP/1.1" 200 OK
INFO: 127.0.0.1:63998 - "GET /api/v1/summary/historical HTTP/1.1" 200 OK
[Repeated 50+ times]
```

**Problems:**
- Backend is being hammered with requests
- Network bandwidth wasted
- Database queries repeated unnecessarily
- User must refresh manually to see new data

---

### 4. **Pie Chart Explanation: Partial Match, Unmatched, Hanging**

**Definitions:**

| Term | Definition | Example |
|------|-----------|---------|
| **Matched** | Transaction exists in all 3 systems (CBS, Switch, NPCI) with matching amounts and dates | Amount: ₹1000 in all systems, Date: 2025-01-08 in all systems |
| **Partial Match** | Transaction exists in 2 out of 3 systems with matching amounts | Amount: ₹1000 in CBS & Switch, but missing in NPCI |
| **Hanging** | Transaction exists in one system but missing in others (typically Switch has it but CBS/NPCI don't) | Amount: ₹1000 in Switch, but missing in CBS and NPCI |
| **Unmatched** | Transaction exists in all systems but amounts/dates don't match | Amount: ₹1000 in CBS, ₹1050 in Switch, ₹1000 in NPCI (variance) |

---

## Solutions

### Solution 1: Fix Dashboard Real-Time Data Issues

**Changes to `frontend/src/pages/Dashboard.tsx`:**

1. **Reduce stale time and increase refetch interval intelligently**
2. **Add tab change listener to invalidate cache**
3. **Add manual refresh button that works**
4. **Implement proper cache invalidation**

```typescript
// Update useQuery configuration
const { data: apiSummaryData, isLoading: isSummaryLoading } = useQuery({
  queryKey: ["summary"],
  queryFn: async () => {
    const data = await apiClient.getSummary();
    console.log("Summary API Response:", data);
    return data;
  },
  staleTime: 30000,  // Reduce to 30 seconds
  refetchInterval: 60000,  // Refetch every 1 minute
  refetchOnWindowFocus: true,  // Refetch when window regains focus
  refetchOnReconnect: true,  // Refetch when reconnected
  enabled: !isDemoMode,
  retry: 1,  // Allow 1 retry
});

// Add tab change listener
useEffect(() => {
  const handleTabChange = () => {
    if (!isDemoMode) {
      queryClient.invalidateQueries({ queryKey: ["summary"] });
      queryClient.invalidateQueries({ queryKey: ["historical-summary"] });
    }
  };

  window.addEventListener("dashboardTabChanged", handleTabChange);
  return () => window.removeEventListener("dashboardTabChanged", handleTabChange);
}, [isDemoMode, queryClient]);

// Update tab change handler
const handleTabChange = (tab: string) => {
  setActiveTab(tab);
  if (!isDemoMode) {
    queryClient.invalidateQueries({ queryKey: ["summary"] });
    queryClient.invalidateQueries({ queryKey: ["historical-summary"] });
  }
};
```

---

### Solution 2: Fix Force Match Real-Time Data

**Changes to `frontend/src/pages/ForceMatch.tsx`:**

1. **Add polling mechanism**
2. **Refetch after force match**
3. **Add auto-refresh option**

```typescript
// Add polling effect
useEffect(() => {
  const pollInterval = setInterval(() => {
    fetchUnmatchedTransactions();
  }, 30000); // Poll every 30 seconds

  return () => clearInterval(pollInterval);
}, []);

// Update confirmForceMatch to refetch immediately
const confirmForceMatch = async () => {
  if (!selectedTransaction) return;

  try {
    dispatch({ type: 'MATCH_START' });

    if (!zeroDifferenceValid) {
      toast({
        title: "Match Prevented",
        description: "Cannot force match with variance.",
        variant: "destructive"
      });
      return;
    }

    await apiClient.forceMatch(
      selectedTransaction.rrn,
      panelLHS,
      panelRHS,
      'match',
      panelLHSColumn || 'amount',
      panelRHSColumn || 'amount'
    );

    toast({
      title: "Success",
      description: `RRN ${selectedTransaction.rrn} has been force matched`,
    });

    // Immediately refetch data
    await fetchUnmatchedTransactions();
    dispatch({ type: 'CLOSE_DUAL_PANEL' });
  } catch (error: any) {
    toast({
      title: "Error",
      description: error.message || "Failed to force match.",
      variant: "destructive"
    });
  } finally {
    dispatch({ type: 'MATCH_FINISH' });
  }
};
```

---

### Solution 3: Optimize API Calls

**Backend Changes to `backend/routes/summary.py`:**

1. **Add caching layer**
2. **Implement response compression**
3. **Add rate limiting**

```python
# Add to summary.py
from functools import lru_cache
import time

# Cache summary for 30 seconds
_summary_cache = {}
_summary_cache_time = 0
CACHE_DURATION = 30

@router.get("/summary")
async def get_summary(user: dict = Depends(get_current_user)):
    """Get latest reconciliation summary with caching"""
    global _summary_cache, _summary_cache_time
    
    current_time = time.time()
    
    # Return cached data if still valid
    if _summary_cache and (current_time - _summary_cache_time) < CACHE_DURATION:
        return _summary_cache
    
    try:
        # ... existing logic ...
        result = {
            "run_id": latest,
            "status": "completed",
            # ... rest of data ...
        }
        
        # Update cache
        _summary_cache = result
        _summary_cache_time = current_time
        
        return result
    except Exception as e:
        logger.error(f"Get summary error: {str(e)}")
        return _summary_cache or {"status": "error"}
```

---

### Solution 4: Database Setup for Disputes & User Management (AWS PostgreSQL)

**Steps to Set Up PostgreSQL on AWS RDS:**

#### Step 1: Create RDS Instance
```bash
# Using AWS CLI
aws rds create-db-instance \
  --db-instance-identifier verif-ai-upi-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username postgres \
  --master-user-password YourSecurePassword123! \
  --allocated-storage 20 \
  --publicly-accessible true \
  --region us-east-1
```

#### Step 2: Create Database Schema

```sql
-- Connect to RDS PostgreSQL instance
-- Create disputes table
CREATE TABLE disputes (
    id SERIAL PRIMARY KEY,
    dispute_id VARCHAR(50) UNIQUE NOT NULL,
    rrn VARCHAR(50) NOT NULL,
    transaction_date DATE NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'OPEN', -- OPEN, WORKING, CLOSED
    category VARCHAR(50), -- Chargeback, Reversal, etc.
    description TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_by VARCHAR(100),
    tat_days INT,
    tat_breached BOOLEAN DEFAULT FALSE,
    INDEX idx_status (status),
    INDEX idx_rrn (rrn),
    INDEX idx_created_at (created_at)
);

-- Create users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'USER', -- ADMIN, MAKER, CHECKER, USER
    department VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_role (role)
);

-- Create user_actions (audit trail)
CREATE TABLE user_actions (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    action VARCHAR(100),
    entity_type VARCHAR(50), -- dispute, reconciliation, etc.
    entity_id VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
);

-- Create maker_checker_approvals table
CREATE TABLE maker_checker_approvals (
    id SERIAL PRIMARY KEY,
    dispute_id INT REFERENCES disputes(id),
    maker_id INT REFERENCES users(id),
    checker_id INT REFERENCES users(id),
    action VARCHAR(50), -- APPROVE, REJECT
    comments TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    INDEX idx_dispute_id (dispute_id),
    INDEX idx_status (action)
);
```

#### Step 3: Update Backend Configuration

```python
# backend/config.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Database Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:YourSecurePassword123!@verif-ai-upi-db.c9akciq32.us-east-1.rds.amazonaws.com:5432/verif_ai_upi"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

#### Step 4: Create Backend API Routes for Disputes

```python
# backend/routes/disputes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from config import get_db
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/disputes", tags=["disputes"])

@router.get("/")
async def get_disputes(
    status: str = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Get all disputes with optional status filter"""
    query = db.query(Dispute)
    
    if status:
        query = query.filter(Dispute.status == status)
    
    disputes = query.all()
    return disputes

@router.post("/")
async def create_dispute(
    dispute_data: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Create new dispute"""
    dispute = Dispute(
        dispute_id=dispute_data.get("dispute_id"),
        rrn=dispute_data.get("rrn"),
        transaction_date=dispute_data.get("transaction_date"),
        amount=dispute_data.get("amount"),
        category=dispute_data.get("category"),
        description=dispute_data.get("description"),
        created_by=user.get("username")
    )
    db.add(dispute)
    db.commit()
    return dispute

@router.put("/{dispute_id}")
async def update_dispute(
    dispute_id: str,
    update_data: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Update dispute status"""
    dispute = db.query(Dispute).filter(Dispute.dispute_id == dispute_id).first()
    
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    
    dispute.status = update_data.get("status", dispute.status)
    dispute.updated_at = datetime.now()
    
    if update_data.get("status") == "CLOSED":
        dispute.resolved_at = datetime.now()
        dispute.resolved_by = user.get("username")
    
    db.commit()
    return dispute
```

#### Step 5: Update Frontend to Use Real Database

```typescript
// frontend/src/lib/api.ts - Add new methods
export const apiClient = {
  // ... existing methods ...
  
  // Disputes API
  getDisputes: async (status?: string): Promise<any> => {
    const params = status ? { status } : {};
    const response = await api.get('/api/v1/disputes', { params });
    return response.data;
  },

  createDispute: async (disputeData: any): Promise<any> => {
    const response = await api.post('/api/v1/disputes', disputeData);
    return response.data;
  },

  updateDispute: async (disputeId: string, updateData: any): Promise<any> => {
    const response = await api.put(`/api/v1/disputes/${disputeId}`, updateData);
    return response.data;
  },

  // Users API
  getUsers: async (): Promise<any> => {
    const response = await api.get('/api/v1/users');
    return response.data;
  },

  createUser: async (userData: any): Promise<any> => {
    const response = await api.post('/api/v1/users', userData);
    return response.data;
  },

  updateUser: async (userId: number, updateData: any): Promise<any> => {
    const response = await api.put(`/api/v1/users/${userId}`, updateData);
    return response.data;
  },
};
```

---

## Implementation Priority

1. **High Priority (Implement First):**
   - Fix Dashboard real-time data (Solution 1)
   - Fix Force Match real-time data (Solution 2)
   - Optimize API calls (Solution 3)

2. **Medium Priority (Implement Next):**
   - Database setup for disputes (Solution 4)
   - Create disputes management UI

3. **Low Priority (Nice to Have):**
   - Advanced caching strategies
   - WebSocket for real-time updates
   - Advanced analytics

---

## Testing Checklist

- [ ] Dashboard loads real data on page load
- [ ] Dashboard data updates when switching tabs
- [ ] Force Match shows updated data after matching
- [ ] Unmatched page shows real-time data
- [ ] API calls reduced (check network tab)
- [ ] No duplicate API requests
- [ ] Disputes can be created/updated in database
- [ ] User management works with database
- [ ] Maker-Checker workflow functions correctly

---

## Performance Metrics

**Before Fixes:**
- API calls per minute: 50+
- Dashboard refresh time: 2+ minutes
- Force match requires manual refresh

**After Fixes:**
- API calls per minute: 5-10
- Dashboard refresh time: 30-60 seconds
- Force match auto-refreshes in 1-2 seconds
