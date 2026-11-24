"""Pydantic v2 Request & Response Data Models for ClaimSense Services & API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TriageDecisionEnum(StrEnum):
    FAST_TRACK = "FAST_TRACK"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    ESCALATE_SIU = "ESCALATE_SIU"


class SystemHealthResponse(BaseModel):
    status: str = Field(description="'HEALTHY' or 'DEGRADED'")
    mode: str = Field(description="'LIVE' or 'OFFLINE_SNAPSHOT'")
    databricks_configured: bool
    groq_configured: bool
    snowflake_configured: bool
    timestamp: str


class KPISummary(BaseModel):
    total_claims: int
    total_claimed_amount: float
    average_claimed_amount: float
    average_reporting_delay_days: float
    high_risk_claims_count: int
    high_risk_rate_percent: float


class ClaimSummary(BaseModel):
    claim_id: str
    policy_id: str
    customer_id: str
    customer_name: str
    claim_type: str
    incident_date: str
    reported_date: str
    claimed_amount: float
    status: str
    city: str
    documents_count: int


class ClaimDetail(ClaimSummary):
    description: str
    customer_risk_score: float
    policy_sum_insured: float
    policy_deductible: float
    policy_status: str
    notes_count: int = 0


class RuleCheckResult(BaseModel):
    rule_id: str
    description: str
    passed: bool
    severity: str
    details: str


class TriageAssessment(BaseModel):
    claim_id: str
    decision: TriageDecisionEnum
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str]
    cited_clause_ids: list[str]
    rule_checks: list[RuleCheckResult]
    needs_human: bool
    trace: list[dict[str, Any]] = Field(default_factory=list)


class HumanReviewRequest(BaseModel):
    action: str = Field(description="'APPROVE', 'OVERRIDE', or 'REJECT'")
    override_decision: TriageDecisionEnum | None = None
    reviewer_notes: str = Field(min_length=3, max_length=1000)


class HumanReviewResponse(BaseModel):
    claim_id: str
    final_decision: TriageDecisionEnum
    reviewer_notes: str
    status: str = "FINALIZED"
    timestamp: str


class PipelineTriggerResponse(BaseModel):
    run_id: str
    status: str
    timestamp: str
    message: str


class AuditRunRecord(BaseModel):
    run_id: str
    run_timestamp: str
    bronze_count: int
    duplicates_count: int
    defects_count: int
    quarantined_total: int
    silver_count: int
    gold_fact_count: int
    discrepancy_count: int
    reconciliation_status: str
    audit_notes: str
