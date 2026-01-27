# UPI Reconciliation System

A comprehensive UPI (Unified Payments Interface) reconciliation system built with FastAPI backend and React frontend.

## Features

- **File Upload & Processing**: Upload and process CBS, Switch, NPCI, and adjustment files
- **Reconciliation Engine**: Automated matching of transactions with configurable tolerance levels
- **Exception Handling**: Robust error handling and recovery mechanisms
- **Audit Trail**: Complete logging and tracking of all system activities
- **GL Proofing**: General Ledger justification and proofing capabilities
- **Rollback Management**: Multi-level rollback functionality for different stages
- **Authentication**: JWT-based secure authentication system
- **Real-time Dashboard**: Comprehensive dashboard with transaction summaries and charts

## Recent Updates

### Authentication System Implementation

#### Backend Changes (app.py)
- **Added JWT Dependencies**: `python-jose[cryptography]`, `passlib[bcrypt]`
- **JWT Authentication Setup**:
  - SECRET_KEY configuration for token signing
  - ALGORITHM = "HS256" for JWT encoding
  - ACCESS_TOKEN_EXPIRE_MINUTES = 30 for token expiration
- **Password Context**: `CryptContext(schemes=["bcrypt"], deprecated="auto")`
- **Password Hashing**: Fixed bcrypt 72-byte limit issue with `"Recon"[:72]`
- **User Database**: Fake user database with hashed passwords
- **Authentication Functions**:
  - `verify_password()`: Verifies plain password against hash
  - `authenticate_user()`: Validates user credentials
  - `create_access_token()`: Generates JWT tokens
- **New API Endpoints**:
  - `POST /api/v1/auth/login`: Accepts username/password, returns JWT token
  - `GET /api/v1/auth/me`: Returns current user info (requires Bearer token)

#### Frontend Changes
- **AuthContext.tsx Updates**:
  - Replaced synchronous login with async API calls
  - Added user state management (username, full_name, email)
  - Implemented token storage in localStorage
  - Added automatic token injection in axios headers
  - Enhanced logout to clear tokens and redirect
- **Layout.tsx Fixes**:
  - Added missing `navigate` and `logout` imports from hooks
  - Fixed handleLogout function to properly call logout and navigate
- **API Client Updates**:
  - Added login method to apiClient object
  - Maintained existing axios instance configuration
- **Error Handling**: Improved error handling for authentication failures

## Installation

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create and activate virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Start the backend server:
```bash
uvicorn app:app --reload
```

The backend will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Authentication

### Default Credentials
- **Username**: `Verif.AI`
- **Password**: `Recon`

### API Endpoints

#### Authentication
- `POST /api/v1/auth/login` - User login
- `GET /api/v1/auth/me` - Get current user info

#### File Operations
- `POST /api/v1/upload` - Upload reconciliation files
- `GET /api/v1/recon/run` - Execute reconciliation process

#### Data Retrieval
- `GET /api/v1/summary` - Get reconciliation summary
- `GET /api/v1/recon/latest/raw` - Get raw transaction data

#### Audit & Logging
- `GET /api/v1/audit/trail/{run_id}` - Get audit trail
- `POST /api/v1/audit/log-action` - Log custom actions

## Project Structure

```
UPI-Recon-main/
├── backend/
│   ├── app.py                 # Main FastAPI application
│   ├── requirements.txt       # Python dependencies
│   ├── config.py             # Configuration settings
│   ├── file_handler.py       # File processing utilities
│   ├── recon_engine.py       # Reconciliation logic
│   ├── audit_trail.py        # Audit logging system
│   └── ...
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── contexts/         # React contexts (AuthContext)
│   │   ├── pages/           # Application pages
│   │   ├── lib/             # Utilities and API client
│   │   └── ...
│   ├── package.json         # Node.js dependencies
│   └── ...
└── README.md               # This file
```

## Key Components

### Backend Components
- **FileHandler**: Manages file uploads and validation
- **ReconciliationEngine**: Core matching algorithm
- **AuditTrail**: Comprehensive logging system
- **RollbackManager**: Multi-level rollback functionality
- **ExceptionHandler**: Error handling and recovery

### Frontend Components
- **AuthContext**: Authentication state management
- **Layout**: Main application layout with navigation
- **Dashboard**: Transaction summary and analytics
- **FileUpload**: File upload interface
- **Recon**: Reconciliation dashboard

## Security Features

- JWT token-based authentication
- Password hashing with bcrypt
- CORS protection
- Request/response interceptors
- Secure token storage

## Development

### Running Tests
```bash
# Backend tests
cd backend
python -m pytest

# Frontend tests
cd frontend
npm test
```

### API Documentation
When the backend is running, visit `http://localhost:8000/docs` for interactive API documentation.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is proprietary software. All rights reserved.

## Support

For support and questions, please contact the development team.
