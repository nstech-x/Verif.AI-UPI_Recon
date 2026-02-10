# Pie Chart Explanation: Transaction Reconciliation States

## Overview

The pie chart in the Dashboard displays the distribution of transactions across three reconciliation states. Understanding these states is critical for effective reconciliation management.

---

## Transaction States Explained

### 1. **MATCHED** (Green) ✅

**Definition:** Transactions that exist in all three systems (CBS, Switch, NPCI) with identical amounts and dates.

**Characteristics:**
- Present in CBS (Core Banking System)
- Present in Switch (Payment Switch)
- Present in NPCI (National Payments Corporation of India)
- Amount matches across all systems
- Date matches across all systems
- Status: Fully reconciled

**Example:**
```
Transaction RRN: 123456789
CBS:   Amount: ₹1,000.00 | Date: 2025-01-08 | Status: MATCHED
Switch: Amount: ₹1,000.00 | Date: 2025-01-08 | Status: MATCHED
NPCI:  Amount: ₹1,000.00 | Date: 2025-01-08 | Status: MATCHED
Result: ✅ MATCHED - No action needed
```

**Action Required:** None - Transaction is fully reconciled

---

### 2. **PARTIAL MATCH** (Purple/Orange) ⚠️

**Definition:** Transactions that exist in 2 out of 3 systems with matching amounts, but missing from one system.

**Characteristics:**
- Present in 2 systems (e.g., CBS + Switch)
- Missing from 1 system (e.g., NPCI)
- Amounts match in the systems where it exists
- Dates match in the systems where it exists
- Status: Partially reconciled

**Example:**
```
Transaction RRN: 987654321
CBS:   Amount: ₹5,000.00 | Date: 2025-01-08 | Status: PRESENT
Switch: Amount: ₹5,000.00 | Date: 2025-01-08 | Status: PRESENT
NPCI:  Amount: ❌ MISSING | Date: ❌ MISSING | Status: NOT FOUND
Result: ⚠️ PARTIAL MATCH - Missing in NPCI
```

**Possible Causes:**
- NPCI file upload failed
- Transaction not yet settled in NPCI
- Data transmission delay
- File format issue

**Action Required:**
- Investigate why transaction is missing in one system
- Check if file was uploaded correctly
- Verify transaction settlement status
- Can be force matched if amounts are identical

---

### 3. **HANGING** (Amber/Red) 🔴

**Definition:** Transactions that exist in only ONE system (typically Switch) but are missing from the other two systems (CBS and NPCI).

**Characteristics:**
- Present in 1 system only (usually Switch)
- Missing from 2 systems (CBS and NPCI)
- Cannot be matched due to missing data
- Status: Unreconciled

**Example:**
```
Transaction RRN: 555666777
CBS:   Amount: ❌ MISSING | Date: ❌ MISSING | Status: NOT FOUND
Switch: Amount: ₹2,500.00 | Date: 2025-01-08 | Status: PRESENT
NPCI:  Amount: ❌ MISSING | Date: ❌ MISSING | Status: NOT FOUND
Result: 🔴 HANGING - Missing in CBS and NPCI
```

**Possible Causes:**
- CBS file upload failed
- NPCI file upload failed
- Transaction not yet processed in CBS
- Duplicate transaction in Switch
- System outage during settlement

**Action Required:**
- Investigate missing systems
- Check file uploads
- Verify transaction status in each system
- May require manual intervention
- Cannot be force matched (insufficient data)

---

### 4. **UNMATCHED** (Red) ❌

**Definition:** Transactions that exist in all three systems BUT have mismatched amounts or dates.

**Characteristics:**
- Present in all 3 systems
- Amount differs across systems
- Date differs across systems
- Status: Reconciliation break

**Example:**
```
Transaction RRN: 111222333
CBS:   Amount: ₹1,000.00 | Date: 2025-01-08 | Status: PRESENT
Switch: Amount: ₹1,050.00 | Date: 2025-01-08 | Status: PRESENT
NPCI:  Amount: ₹1,000.00 | Date: 2025-01-09 | Status: PRESENT
Result: ❌ UNMATCHED - Amount variance (₹50) and date variance (1 day)
```

**Possible Causes:**
- Amount variance due to:
  - Rounding differences
  - Fee deductions
  - Currency conversion
  - Data entry error
- Date variance due to:
  - Processing delays
  - Time zone differences
  - Settlement date vs. transaction date
  - System clock issues

**Action Required:**
- Investigate variance reason
- Determine if variance is acceptable
- Use Force Match tool if variance is justified
- Create exception record if variance cannot be resolved
- May require manual approval

---

## Reconciliation Flow Chart

```
Transaction Received
        ↓
    ┌───────────────────────────────────────┐
    │ Check if in all 3 systems?            │
    └───────────────────────────────────────┘
         ↙                    ↘
       YES                     NO
        ↓                      ↓
    ┌─────────────┐      ┌──────────────────┐
    │ Check if    │      │ Check if in 2    │
    │ amounts &   │      │ systems?         │
    │ dates match?│      └──────────────────┘
    └─────────────┘           ↙        ↘
         ↙        ↘          YES        NO
       YES        NO          ↓         ↓
        ↓          ↓      ┌────────┐  ┌─────────┐
    ┌────────┐  ┌──────┐ │PARTIAL │  │HANGING  │
    │MATCHED │  │UNMATCH│ │MATCH   │  │         │
    │   ✅   │  │  ❌   │ └────────┘  └─────────┘
    └────────┘  └──────┘
```

---

## Dashboard Pie Chart Interpretation

### Example Dashboard Snapshot:

```
Total Transactions: 10,000

Pie Chart Distribution:
├─ Matched:        8,500 (85%) ✅ GREEN
├─ Partial Match:  1,000 (10%) ⚠️  ORANGE
├─ Hanging:          300 (3%)  🔴 RED
└─ Unmatched:        200 (2%)  ❌ DARK RED
```

### What This Means:

| Metric | Value | Interpretation |
|--------|-------|-----------------|
| **Matched** | 8,500 (85%) | Excellent - Most transactions reconciled |
| **Partial Match** | 1,000 (10%) | Good - Can be investigated and resolved |
| **Hanging** | 300 (3%) | Concerning - Missing data in systems |
| **Unmatched** | 200 (2%) | Critical - Requires investigation |

### Reconciliation Health Score:

```
Health = (Matched / Total) × 100
Health = (8,500 / 10,000) × 100 = 85%

Status: ✅ HEALTHY (Target: >95%)
```

---

## Action Items by State

### For MATCHED Transactions (85%)
- ✅ No action needed
- Archive and close
- Use as baseline for comparison

### For PARTIAL MATCH Transactions (10%)
- ⚠️ Investigate missing system
- Check file uploads
- Verify settlement status
- Can use Force Match if amounts match
- Target: Resolve within 24 hours

### For HANGING Transactions (3%)
- 🔴 High priority investigation
- Check all three systems
- Verify file uploads
- May require manual intervention
- Target: Resolve within 48 hours

### For UNMATCHED Transactions (2%)
- ❌ Critical - Requires immediate action
- Analyze variance reason
- Determine if acceptable
- Use Force Match with justification
- Create exception record
- Target: Resolve within 24 hours

---

## Force Match Scenarios

### When to Use Force Match:

✅ **ALLOWED:**
- Partial Match with zero difference in matching systems
- Unmatched with acceptable variance (e.g., rounding)
- Hanging with sufficient evidence

❌ **NOT ALLOWED:**
- Unmatched with significant variance (>1%)
- Hanging with no supporting evidence
- Transactions with missing critical data

### Force Match Example:

```
Transaction: RRN 123456789
CBS:   ₹1,000.00
Switch: ₹1,000.00
NPCI:  ₹1,000.00

Status: PARTIAL MATCH (missing in one system)
Action: ✅ Can Force Match (zero difference)
```

---

## Monitoring & Alerts

### Green Zone (Healthy):
- Matched: > 90%
- Partial Match: < 5%
- Hanging: < 2%
- Unmatched: < 3%

### Yellow Zone (Warning):
- Matched: 80-90%
- Partial Match: 5-10%
- Hanging: 2-5%
- Unmatched: 3-5%

### Red Zone (Critical):
- Matched: < 80%
- Partial Match: > 10%
- Hanging: > 5%
- Unmatched: > 5%

---

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| High Hanging % | File upload failed | Re-upload files |
| High Unmatched % | Amount variance | Investigate variance reason |
| Stuck Partial Match | Missing system data | Check system status |
| Sudden drop in Matched % | System outage | Wait for system recovery |

---

## Best Practices

1. **Daily Monitoring**
   - Check pie chart daily
   - Monitor trend over time
   - Alert if metrics degrade

2. **Timely Resolution**
   - Resolve Partial Match within 24 hours
   - Resolve Hanging within 48 hours
   - Resolve Unmatched within 24 hours

3. **Documentation**
   - Document all force matches
   - Record variance reasons
   - Maintain audit trail

4. **Escalation**
   - Escalate if Matched < 80%
   - Escalate if Hanging > 5%
   - Escalate if Unmatched > 5%

---

## Summary Table

| State | Color | Systems | Amounts | Dates | Action | Priority |
|-------|-------|---------|---------|-------|--------|----------|
| Matched | 🟢 Green | 3/3 | ✅ Match | ✅ Match | None | Low |
| Partial Match | 🟠 Orange | 2/3 | ✅ Match | ✅ Match | Investigate | Medium |
| Hanging | 🔴 Red | 1/3 | N/A | N/A | Investigate | High |
| Unmatched | 🔴 Dark Red | 3/3 | ❌ Differ | ❌ Differ | Investigate | Critical |

---

## Questions?

For more information, refer to:
- Dashboard documentation
- Force Match guide
- Reconciliation process documentation
- System administrator guide
