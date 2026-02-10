# File Upload & Dashboard Enhancement – Implementation Prompt

You are working on an existing web application (frontend + backend).  
Do NOT change existing business logic or core code unless explicitly required.  
Only implement the changes described below, preserving current architecture, APIs, and behavior.
---
## 1) File Upload Module Changes
### 1.1 Bulk Upload Enhancement (NPCI, NTSL, Adjustment)
Implement bulk upload for the following modules:
- NPCI
- NTSL
- Adjustment

#### Requirements
##### A) Cycle Selection (Optional)
- Multi-select cycle dropdown is **optional** due to the new file-based cycle identification system.
- If present, it should allow selecting multiple cycles.
- The system must not depend on manual cycle selection for processing files.
- Primary cycle identification must come from:
  - File name, or
  - File content.

##### B) File Naming Convention
Each uploaded file must follow this pattern:
Example:

Where:
- `cycleNo` = cycle1, cycle2, etc.
- `type` = inward | outward
- `date` = DDMMYYYY
- `filename` = original file name (not sure can be there consider both case)
Example: 
- Filename: cycle1_inward_06062026_NPCI
- Filename: cycle1_inward_06062026

##### C) Date Validation Rule
- The date extracted from the file name must be:
  - Current date (T date) only.
- Reject files with:
  - T-1 date (previous day)
  - T+1 date (future date)

##### D) Cycle Filter Removal
- Remove cycle filter from UI for NPCI and NTSL.
- Cycle must be identified from:
  - File name, or
  - File content.
- UI should not require manual cycle selection for differentiation.
---

### 1.2 Move Switch Upload to CBS Tab
- Remove "Switch Upload" from its current location.
- Move "Switch Upload" into the **CBS tab**.
- Ensure existing functionality remains unchanged.
---

## 2) Income & Expense Dashboard Changes
- Move "Income & Expense Dashboard" into the **Main Dashboard**.
- Create a new tab named:
- Place it next to:

Constraints:
- Do not modify existing charts, APIs, or calculations.
- Only change navigation and layout.
---

## 3) User Management Renaming
- Rename:
Scope:
- Update UI labels, menu names, and tab titles only.
- Do NOT change backend logic, routes, or permissions.
---

## 4) NPCI Cycle Page Movement & File Upload
### Requirements
#### A) Page Movement
- Move "NPCI Cycle" page into:

#### B) File Upload Extension
- Add a new upload option:
  - Allow uploading any type of file (no strict validation for now).
- Keep it generic (accept all file formats).

Constraints:
- Do not break existing NPCI cycle logic.
- Only relocate the page and extend upload capability.
---

## Technical Constraints
- Do NOT refactor or rewrite existing modules unnecessarily.
- Do NOT change database schema unless required.
- Maintain current API contracts.
- Focus only on:
  - UI relocation
  - Validation logic
  - Tab restructuring
  - Naming changes
  - File upload behavior

---

## Expected Output
1. Updated UI structure (tabs & navigation)
2. Modified file upload logic
3. Filename-based cycle and date validation
4. Minimal code changes only where required
5. No unrelated optimizations or redesigns
