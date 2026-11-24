# Escalation Trace Analysis (Phase 1 / ISS-01)

Diagnostic trace for the 10 expected `ESCALATE_SIU` cases.

## EVAL-036: CLM-30008
- **Expected Decision**: `ESCALATE_SIU`
- **Actual Decision**: `NEEDS_REVIEW`
- **Customer Risk Score**: `0.94`
- **Flag High Risk Customer**: `1`
- **Rule Validation Results**:
  - `RULE-01-ACTIVE-PERIOD` (CRITICAL): PASS - Incident: 2025-12-26 | Term: 2025-08-20 to 2026-02-16 (Status: ACTIVE)
  - `RULE-02-SUM-INSURED` (HIGH): PASS - Claimed: $34,101.36 | Limit: $350,000.00
  - `RULE-03-MANDATORY-DOCS` (MEDIUM): FAIL - Attached documents: 1 (Required: >= 2)
  - `RULE-04-TIMELY-REPORTING` (MEDIUM): FAIL - Reporting delay: 15 calendar days
  - `RULE-05-FRAUD-RISK` (HIGH): FAIL - Risk score: 0.94 (Threshold: 0.60)
- **Routing Execution Trace**:
  - Node `intake`: result=VALIDATED
  - Node `fetch_data`: result=SUCCESS
  - Node `validate_rules`: result=None
  - Node `retrieve_clauses`: result=None
  - Node `assess`: result=NEEDS_REVIEW

---

## EVAL-037: CLM-30010
- **Expected Decision**: `ESCALATE_SIU`
- **Actual Decision**: `NEEDS_REVIEW`
- **Customer Risk Score**: `0.93`
- **Flag High Risk Customer**: `1`
- **Rule Validation Results**:
  - `RULE-01-ACTIVE-PERIOD` (CRITICAL): FAIL - Incident: 2025-02-24 | Term: 2025-04-25 to 2026-04-25 (Status: ACTIVE)
  - `RULE-02-SUM-INSURED` (HIGH): PASS - Claimed: $31,069.44 | Limit: $150,000.00
  - `RULE-03-MANDATORY-DOCS` (MEDIUM): FAIL - Attached documents: 1 (Required: >= 2)
  - `RULE-04-TIMELY-REPORTING` (MEDIUM): FAIL - Reporting delay: 443 calendar days
  - `RULE-05-FRAUD-RISK` (HIGH): FAIL - Risk score: 0.93 (Threshold: 0.60)
- **Routing Execution Trace**:
  - Node `intake`: result=VALIDATED
  - Node `fetch_data`: result=SUCCESS
  - Node `validate_rules`: result=None
  - Node `retrieve_clauses`: result=None
  - Node `assess`: result=NEEDS_REVIEW

---

## EVAL-038: CLM-30011
- **Expected Decision**: `ESCALATE_SIU`
- **Actual Decision**: `NEEDS_REVIEW`
- **Customer Risk Score**: `0.93`
- **Flag High Risk Customer**: `1`
- **Rule Validation Results**:
  - `RULE-01-ACTIVE-PERIOD` (CRITICAL): FAIL - Incident: 2026-05-10 | Term: 2025-04-25 to 2026-04-25 (Status: ACTIVE)
  - `RULE-02-SUM-INSURED` (HIGH): PASS - Claimed: $12,434.02 | Limit: $150,000.00
  - `RULE-03-MANDATORY-DOCS` (MEDIUM): PASS - Attached documents: 4 (Required: >= 2)
  - `RULE-04-TIMELY-REPORTING` (MEDIUM): PASS - Reporting delay: 1 calendar days
  - `RULE-05-FRAUD-RISK` (HIGH): FAIL - Risk score: 0.93 (Threshold: 0.60)
- **Routing Execution Trace**:
  - Node `intake`: result=VALIDATED
  - Node `fetch_data`: result=SUCCESS
  - Node `validate_rules`: result=None
  - Node `retrieve_clauses`: result=None
  - Node `assess`: result=NEEDS_REVIEW

---

## EVAL-039: CLM-30012
- **Expected Decision**: `ESCALATE_SIU`
- **Actual Decision**: `NEEDS_REVIEW`
- **Customer Risk Score**: `0.93`
- **Flag High Risk Customer**: `1`
- **Rule Validation Results**:
  - `RULE-01-ACTIVE-PERIOD` (CRITICAL): FAIL - Incident: 2026-05-08 | Term: 2025-04-25 to 2026-04-25 (Status: ACTIVE)
  - `RULE-02-SUM-INSURED` (HIGH): PASS - Claimed: $39,424.99 | Limit: $150,000.00
  - `RULE-03-MANDATORY-DOCS` (MEDIUM): PASS - Attached documents: 3 (Required: >= 2)
  - `RULE-04-TIMELY-REPORTING` (MEDIUM): PASS - Reporting delay: 1 calendar days
  - `RULE-05-FRAUD-RISK` (HIGH): FAIL - Risk score: 0.93 (Threshold: 0.60)
- **Routing Execution Trace**:
  - Node `intake`: result=VALIDATED
  - Node `fetch_data`: result=SUCCESS
  - Node `validate_rules`: result=None
  - Node `retrieve_clauses`: result=None
  - Node `assess`: result=NEEDS_REVIEW

---

## EVAL-040: CLM-30013
- **Expected Decision**: `ESCALATE_SIU`
- **Actual Decision**: `NEEDS_REVIEW`
- **Customer Risk Score**: `0.93`
- **Flag High Risk Customer**: `1`
- **Rule Validation Results**:
  - `RULE-01-ACTIVE-PERIOD` (CRITICAL): FAIL - Incident: 2026-05-06 | Term: 2025-04-25 to 2026-04-25 (Status: ACTIVE)
  - `RULE-02-SUM-INSURED` (HIGH): PASS - Claimed: $56,129.07 | Limit: $150,000.00
  - `RULE-03-MANDATORY-DOCS` (MEDIUM): PASS - Attached documents: 3 (Required: >= 2)
  - `RULE-04-TIMELY-REPORTING` (MEDIUM): PASS - Reporting delay: 1 calendar days
  - `RULE-05-FRAUD-RISK` (HIGH): FAIL - Risk score: 0.93 (Threshold: 0.60)
- **Routing Execution Trace**:
  - Node `intake`: result=VALIDATED
  - Node `fetch_data`: result=SUCCESS
  - Node `validate_rules`: result=None
  - Node `retrieve_clauses`: result=None
  - Node `assess`: result=NEEDS_REVIEW

---

## EVAL-041: CLM-30016
- **Expected Decision**: `ESCALATE_SIU`
- **Actual Decision**: `NEEDS_REVIEW`
- **Customer Risk Score**: `0.93`
- **Flag High Risk Customer**: `1`
- **Rule Validation Results**:
  - `RULE-01-ACTIVE-PERIOD` (CRITICAL): PASS - Incident: 2025-11-03 | Term: 2025-04-25 to 2026-04-25 (Status: ACTIVE)
  - `RULE-02-SUM-INSURED` (HIGH): PASS - Claimed: $63,102.46 | Limit: $150,000.00
  - `RULE-03-MANDATORY-DOCS` (MEDIUM): PASS - Attached documents: 2 (Required: >= 2)
  - `RULE-04-TIMELY-REPORTING` (MEDIUM): PASS - Reporting delay: 2 calendar days
  - `RULE-05-FRAUD-RISK` (HIGH): FAIL - Risk score: 0.93 (Threshold: 0.60)
- **Routing Execution Trace**:
  - Node `intake`: result=VALIDATED
  - Node `fetch_data`: result=SUCCESS
  - Node `validate_rules`: result=None
  - Node `retrieve_clauses`: result=None
  - Node `assess`: result=NEEDS_REVIEW

---

## EVAL-042: CLM-30017
- **Expected Decision**: `ESCALATE_SIU`
- **Actual Decision**: `NEEDS_REVIEW`
- **Customer Risk Score**: `0.93`
- **Flag High Risk Customer**: `1`
- **Rule Validation Results**:
  - `RULE-01-ACTIVE-PERIOD` (CRITICAL): PASS - Incident: 2026-01-04 | Term: 2025-07-12 to 2026-01-08 (Status: ACTIVE)
  - `RULE-02-SUM-INSURED` (HIGH): PASS - Claimed: $123,064.78 | Limit: $250,000.00
  - `RULE-03-MANDATORY-DOCS` (MEDIUM): FAIL - Attached documents: 1 (Required: >= 2)
  - `RULE-04-TIMELY-REPORTING` (MEDIUM): FAIL - Reporting delay: 20 calendar days
  - `RULE-05-FRAUD-RISK` (HIGH): FAIL - Risk score: 0.93 (Threshold: 0.60)
- **Routing Execution Trace**:
  - Node `intake`: result=VALIDATED
  - Node `fetch_data`: result=SUCCESS
  - Node `validate_rules`: result=None
  - Node `retrieve_clauses`: result=None
  - Node `assess`: result=NEEDS_REVIEW

---

## EVAL-043: CLM-30021
- **Expected Decision**: `ESCALATE_SIU`
- **Actual Decision**: `NEEDS_REVIEW`
- **Customer Risk Score**: `0.77`
- **Flag High Risk Customer**: `1`
- **Rule Validation Results**:
  - `RULE-01-ACTIVE-PERIOD` (CRITICAL): PASS - Incident: 2025-10-26 | Term: 2025-08-25 to 2026-02-21 (Status: ACTIVE)
  - `RULE-02-SUM-INSURED` (HIGH): PASS - Claimed: $62,497.65 | Limit: $250,000.00
  - `RULE-03-MANDATORY-DOCS` (MEDIUM): FAIL - Attached documents: 1 (Required: >= 2)
  - `RULE-04-TIMELY-REPORTING` (MEDIUM): FAIL - Reporting delay: 19 calendar days
  - `RULE-05-FRAUD-RISK` (HIGH): FAIL - Risk score: 0.77 (Threshold: 0.60)
- **Routing Execution Trace**:
  - Node `intake`: result=VALIDATED
  - Node `fetch_data`: result=SUCCESS
  - Node `validate_rules`: result=None
  - Node `retrieve_clauses`: result=None
  - Node `assess`: result=NEEDS_REVIEW

---

## EVAL-044: CLM-30023
- **Expected Decision**: `ESCALATE_SIU`
- **Actual Decision**: `NEEDS_REVIEW`
- **Customer Risk Score**: `0.77`
- **Flag High Risk Customer**: `1`
- **Rule Validation Results**:
  - `RULE-01-ACTIVE-PERIOD` (CRITICAL): PASS - Incident: 2026-02-19 | Term: 2025-08-25 to 2026-02-21 (Status: ACTIVE)
  - `RULE-02-SUM-INSURED` (HIGH): PASS - Claimed: $84,168.77 | Limit: $250,000.00
  - `RULE-03-MANDATORY-DOCS` (MEDIUM): PASS - Attached documents: 4 (Required: >= 2)
  - `RULE-04-TIMELY-REPORTING` (MEDIUM): PASS - Reporting delay: 1 calendar days
  - `RULE-05-FRAUD-RISK` (HIGH): FAIL - Risk score: 0.77 (Threshold: 0.60)
- **Routing Execution Trace**:
  - Node `intake`: result=VALIDATED
  - Node `fetch_data`: result=SUCCESS
  - Node `validate_rules`: result=None
  - Node `retrieve_clauses`: result=None
  - Node `assess`: result=NEEDS_REVIEW

---

## EVAL-045: CLM-30028
- **Expected Decision**: `ESCALATE_SIU`
- **Actual Decision**: `NEEDS_REVIEW`
- **Customer Risk Score**: `0.61`
- **Flag High Risk Customer**: `0`
- **Rule Validation Results**:
  - `RULE-01-ACTIVE-PERIOD` (CRITICAL): FAIL - Incident: 2025-12-01 | Term: 2026-01-12 to 2028-01-12 (Status: ACTIVE)
  - `RULE-02-SUM-INSURED` (HIGH): PASS - Claimed: $23,819.09 | Limit: $50,000.00
  - `RULE-03-MANDATORY-DOCS` (MEDIUM): PASS - Attached documents: 4 (Required: >= 2)
  - `RULE-04-TIMELY-REPORTING` (MEDIUM): FAIL - Reporting delay: 15 calendar days
  - `RULE-05-FRAUD-RISK` (HIGH): FAIL - Risk score: 0.61 (Threshold: 0.60)
- **Routing Execution Trace**:
  - Node `intake`: result=VALIDATED
  - Node `fetch_data`: result=SUCCESS
  - Node `validate_rules`: result=None
  - Node `retrieve_clauses`: result=None
  - Node `assess`: result=NEEDS_REVIEW

---
