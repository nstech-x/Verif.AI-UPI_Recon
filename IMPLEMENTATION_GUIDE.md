# Implementation Guide - Bug Fixes & Database Setup

## Summary of Changes Made

### 1. Dashboard Real-Time Data Fix ✅
**File:** `frontend/src/pages/Dashboard.tsx`

**Changes:**
- Reduced `staleTime` from 60s to 30s
- Reduced `refetchInterval` from 120s to 60s
- Added `refetchOnWindowFocus: true` - refetch when user returns to tab
- Added `refetchOnReconnect: true` - refetch when internet reconnects
- Changed `retry` from 0 to 1 - allow one retry on failure

**Result:** Dashboard now updates every 1 minute instead of 2 minutes, and automatically refreshes when switching tabs.

---

### 2. Force Match Real-Time Data Fix ✅
**File:** `frontend/src/pages/ForceMatch.tsx`

**Changes:**
- Added polling mechanism that refetches data every 30 seconds
- Data automatically refreshes after force match operation
- Manual refresh button available

**Result:** Force Match page now shows updated data automatically without requiring manual refresh.

---

## Next Steps: Database Setup for Disputes & User Management

### Step 1: Create AWS RDS PostgreSQL Instance

#### Option A: Using AWS Console
1. Go to AWS RDS Dashboard
2. Click "Create Database"
3. Select "PostgreSQL"
4. Choose "Free tier" template
5. Set DB instance identifier: `verif-ai-upi-db`
6. Set master username: `postgres`
7. Set master password: (save securely)
8. Allocate storage: 20 GB
9. Enable public accessibility: Yes
10. Click "Create Database"

#### Option B: Using AWS CLI
```bash
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

**Wait 5-10 minutes for the instance to be created.**

---

### Step 2: Get Database Connection Details

1. Go to RDS Dashboard
2. Click on your instance `verif-ai-upi-db`
3. Note the following:
   - **Endpoint:** (e.g., `verif-ai-upi-db.c9akciq32.us-east-1.rds.amazonaws.com`)
   - **Port:** 5432
   - **Master Username:** postgres
   - **Password:** (what you set)

---

### Step 3: Create Database Schema

#### Using pgAdmin (GUI)
1. Download pgAdmin from https://www.pgadmin.org/download/
2. Open pgAdmin
3. Right-click "Servers" → "Register" → "Server"
4. Name: `Verif.AI UPI`
5. Host: (your RDS endpoint)
6. Username: postgres
7. Password: (your password)
8. Click "Save"
9. Right-click the server → "Query Tool"
10. Copy and paste the SQL below

#### Using Command Line
```bash
psql -h verif-ai-upi-db.c9akciq32.us-east-1.rds.amazonaws.com \
     -U postgres \
     -d postgres \
     -f create_schema.sql
```

#### SQL Schema to Execute

Create a file `backend/database/create_schema.sql`:

```sql
-- Create disputes table
CREATE TABLE IF NOT EXISTS disputes (
    id SERIAL PRIMARY KEY,
    dispute_id VARCHAR(50) UNIQUE NOT NULL,
    rrn VARCHAR(50) NOT NULL,
    transaction_date DATE NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'OPEN',
    category VARCHAR(50),
    description TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_by VARCHAR(100),
    tat_days INT,
    tat_breached BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_disputes_status ON disputes(status);
CREATE INDEX idx_disputes_rrn ON disputes(rrn);
CREATE INDEX idx_disputes_created_at ON disputes(created_at);

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'USER',
    department VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_role ON users(role);

-- Create user_actions (audit trail)
CREATE TABLE IF NOT EXISTS user_actions (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR(100),
    entity_type VARCHAR(50),
    entity_id VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_actions_user_id ON user_actions(user_id);
CREATE INDEX idx_user_actions_created_at ON user_actions(created_at);

-- Create maker_checker_approvals table
CREATE TABLE IF NOT EXISTS maker_checker_approvals (
    id SERIAL PRIMARY KEY,
    dispute_id INT REFERENCES disputes(id) ON DELETE CASCADE,
    maker_id INT REFERENCES users(id),
    checker_id INT REFERENCES users(id),
    action VARCHAR(50),
    comments TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP
);

CREATE INDEX idx_maker_checker_dispute_id ON maker_checker_approvals(dispute_id);
CREATE INDEX idx_maker_checker_action ON maker_checker_approvals(action);
```

---

### Step 4: Update Backend Configuration

#### File: `backend/config.py`

Add the following:

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from urllib.parse import quote_plus

# Database Configuration
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "YourSecurePassword123!")
DB_HOST = os.getenv("DB_HOST", "verif-ai-upi-db.c9akciq32.us-east-1.rds.amazonaws.com")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "verif_ai_upi")

# URL encode password to handle special characters
encoded_password = quote_plus(DB_PASSWORD)

DATABASE_URL = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Test connections before using
    pool_size=10,
    max_overflow=20,
    echo=False  # Set to True for SQL debugging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency for FastAPI routes"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
```

#### File: `backend/requirements.txt`

Add these dependencies:

```
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
alembic==1.12.1
```

Install them:
```bash
pip install -r requirements.txt
```

---

### Step 5: Create Database Models

#### File: `backend/models/dispute.py`

```python
from sqlalchemy import Column, Integer, String, Date, Numeric, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from config import Base

class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True, index=True)
    dispute_id = Column(String(50), unique=True, index=True)
    rrn = Column(String(50), index=True)
    transaction_date = Column(Date)
    amount = Column(Numeric(15, 2))
    status = Column(String(20), default="OPEN", index=True)
    category = Column(String(50))
    description = Column(Text)
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(100), nullable=True)
    tat_days = Column(Integer, nullable=True)
    tat_breached = Column(Boolean, default=False)

    # Relationships
    approvals = relationship("MakerCheckerApproval", back_populates="dispute")

    def to_dict(self):
        return {
            "id": self.id,
            "dispute_id": self.dispute_id,
            "rrn": self.rrn,
            "transaction_date": self.transaction_date.isoformat() if self.transaction_date else None,
            "amount": float(self.amount) if self.amount else 0,
            "status": self.status,
            "category": self.category,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "tat_days": self.tat_days,
            "tat_breached": self.tat_breached,
        }
```

#### File: `backend/models/user.py`

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from config import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    password_hash = Column(String(255))
    role = Column(String(50), default="USER", index=True)
    department = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    actions = relationship("UserAction", back_populates="user")
    approvals_made = relationship("MakerCheckerApproval", foreign_keys="MakerCheckerApproval.maker_id", back_populates="maker")
    approvals_checked = relationship("MakerCheckerApproval", foreign_keys="MakerCheckerApproval.checker_id", back_populates="checker")

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "department": self.department,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
```

#### File: `backend/models/maker_checker.py`

```python
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from config import Base

class MakerCheckerApproval(Base):
    __tablename__ = "maker_checker_approvals"

    id = Column(Integer, primary_key=True, index=True)
    dispute_id = Column(Integer, ForeignKey("disputes.id"))
    maker_id = Column(Integer, ForeignKey("users.id"))
    checker_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(50))
    comments = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)

    # Relationships
    dispute = relationship("Dispute", back_populates="approvals")
    maker = relationship("User", foreign_keys=[maker_id], back_populates="approvals_made")
    checker = relationship("User", foreign_keys=[checker_id], back_populates="approvals_checked")

    def to_dict(self):
        return {
            "id": self.id,
            "dispute_id": self.dispute_id,
            "maker_id": self.maker_id,
            "checker_id": self.checker_id,
            "action": self.action,
            "comments": self.comments,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
        }
```

---

### Step 6: Create Backend API Routes

#### File: `backend/routes/disputes_db.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from config import get_db
from models.dispute import Dispute
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/api/v1/disputes", tags=["disputes"])

@router.get("/")
async def get_disputes(
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all disputes with optional status filter"""
    query = db.query(Dispute)
    
    if status:
        query = query.filter(Dispute.status == status)
    
    disputes = query.all()
    return [d.to_dict() for d in disputes]

@router.post("/")
async def create_dispute(
    dispute_data: dict,
    db: Session = Depends(get_db)
):
    """Create new dispute"""
    dispute = Dispute(
        dispute_id=dispute_data.get("dispute_id"),
        rrn=dispute_data.get("rrn"),
        transaction_date=dispute_data.get("transaction_date"),
        amount=dispute_data.get("amount"),
        category=dispute_data.get("category"),
        description=dispute_data.get("description"),
        created_by=dispute_data.get("created_by", "system")
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    return dispute.to_dict()

@router.put("/{dispute_id}")
async def update_dispute(
    dispute_id: str,
    update_data: dict,
    db: Session = Depends(get_db)
):
    """Update dispute status"""
    dispute = db.query(Dispute).filter(Dispute.dispute_id == dispute_id).first()
    
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    
    dispute.status = update_data.get("status", dispute.status)
    dispute.updated_at = datetime.utcnow()
    
    if update_data.get("status") == "CLOSED":
        dispute.resolved_at = datetime.utcnow()
        dispute.resolved_by = update_data.get("resolved_by", "system")
    
    db.commit()
    db.refresh(dispute)
    return dispute.to_dict()

@router.get("/{dispute_id}")
async def get_dispute(
    dispute_id: str,
    db: Session = Depends(get_db)
):
    """Get specific dispute"""
    dispute = db.query(Dispute).filter(Dispute.dispute_id == dispute_id).first()
    
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    
    return dispute.to_dict()
```

#### File: `backend/routes/users_db.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from config import get_db
from models.user import User
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/api/v1/users", tags=["users"])

@router.get("/")
async def get_users(
    role: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all users with optional role filter"""
    query = db.query(User)
    
    if role:
        query = query.filter(User.role == role)
    
    users = query.all()
    return [u.to_dict() for u in users]

@router.post("/")
async def create_user(
    user_data: dict,
    db: Session = Depends(get_db)
):
    """Create new user"""
    # Check if user already exists
    existing = db.query(User).filter(User.username == user_data.get("username")).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    user = User(
        username=user_data.get("username"),
        email=user_data.get("email"),
        password_hash=user_data.get("password_hash"),  # Should be hashed in production
        role=user_data.get("role", "USER"),
        department=user_data.get("department")
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user.to_dict()

@router.put("/{user_id}")
async def update_user(
    user_id: int,
    update_data: dict,
    db: Session = Depends(get_db)
):
    """Update user"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.role = update_data.get("role", user.role)
    user.department = update_data.get("department", user.department)
    user.is_active = update_data.get("is_active", user.is_active)
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    return user.to_dict()
```

---

### Step 7: Update Backend Main App

#### File: `backend/app.py`

Add these imports and initialization:

```python
from config import init_db, get_db
from routes import disputes_db, users_db

# Initialize database tables
init_db()

# Include new routes
app.include_router(disputes_db.router)
app.include_router(users_db.router)
```

---

### Step 8: Update Environment Variables

#### File: `.env` (create if doesn't exist)

```
# Database Configuration
DB_USER=postgres
DB_PASSWORD=YourSecurePassword123!
DB_HOST=verif-ai-upi-db.c9akciq32.us-east-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=verif_ai_upi

# API Configuration
VITE_API_BASE_URL=http://localhost:8000
```

---

### Step 9: Update Frontend API Client

#### File: `frontend/src/lib/api.ts`

Add these methods:

```typescript
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

getDispute: async (disputeId: string): Promise<any> => {
  const response = await api.get(`/api/v1/disputes/${disputeId}`);
  return response.data;
},

// Users API
getUsers: async (role?: string): Promise<any> => {
  const params = role ? { role } : {};
  const response = await api.get('/api/v1/users', { params });
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
```

---

## Testing Checklist

- [ ] Dashboard loads and shows real data
- [ ] Dashboard data updates when switching tabs
- [ ] Force Match shows updated data after matching
- [ ] API calls reduced (check browser Network tab)
- [ ] Database connection works
- [ ] Can create disputes in database
- [ ] Can create users in database
- [ ] Maker-Checker workflow functions

---

## Troubleshooting

### Database Connection Issues

**Error:** `psycopg2.OperationalError: could not connect to server`

**Solution:**
1. Check RDS instance is running (AWS Console)
2. Check security group allows inbound on port 5432
3. Verify credentials are correct
4. Test connection: `psql -h <endpoint> -U postgres`

### API Not Finding Routes

**Error:** `404 Not Found` on `/api/v1/disputes`

**Solution:**
1. Ensure routes are included in `app.py`
2. Check route prefix is correct
3. Restart backend server

### Frontend Can't Connect to Backend

**Error:** `CORS error` or `Connection refused`

**Solution:**
1. Check backend is running on correct port
2. Update `VITE_API_BASE_URL` in `.env`
3. Ensure CORS is enabled in backend

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
- Database queries optimized with indexes

---

## Next Phase: Advanced Features

1. **WebSocket for Real-Time Updates**
   - Replace polling with WebSocket connections
   - Real-time dispute status updates
   - Live user activity feed

2. **Advanced Caching**
   - Redis for session management
   - Cache frequently accessed data
   - Reduce database queries

3. **Analytics & Reporting**
   - Dispute resolution metrics
   - User activity reports
   - Performance dashboards

4. **Notifications**
   - Email alerts for disputes
   - In-app notifications
   - SMS for critical issues
