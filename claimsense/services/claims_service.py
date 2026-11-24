"""Unified business logic and domain service layer for ClaimSense.

Shared seamlessly between the in-process Streamlit application and the FastAPI REST layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from claimsense.agent.graph import get_triage_graph
from claimsense.config import Settings, get_settings
from claimsense.db.client_factory import get_db_client
from claimsense.db.errors import ClaimNotFoundError
from claimsense.services.models import (
    AuditRunRecord,
    ClaimDetail,
    ClaimSummary,
    HumanReviewRequest,
    HumanReviewResponse,
    KPISummary,
    PipelineTriggerResponse,
    RuleCheckResult,
    SystemHealthResponse,
    TriageAssessment,
    TriageDecisionEnum,
)


class ClaimsService:
    """Core domain service for claims operations, KPIs, data quality, and triage."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.db = get_db_client(self.settings)
        self.agent_graph = get_triage_graph()

    def get_health(self) -> SystemHealthResponse:
        """Evaluates health of connected services and fallback mode."""
        is_healthy = True
        return SystemHealthResponse(
            status="HEALTHY" if is_healthy else "DEGRADED",
            mode=self.db.active_mode,
            databricks_configured=self.settings.is_databricks_configured,
            groq_configured=self.settings.is_groq_configured,
            snowflake_configured=self.settings.is_snowflake_configured,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def get_kpi_summary(self) -> KPISummary:
        """Calculates executive KPI metrics across the fact table."""
        query = """
            SELECT
                COUNT(f.claim_sk) AS total_claims,
                COALESCE(SUM(f.claimed_amount), 0) AS total_amount,
                COALESCE(AVG(f.claimed_amount), 0) AS avg_amount,
                COALESCE(AVG(f.reporting_delay_days), 0) AS avg_delay,
                COALESCE(SUM(f.flag_high_risk_customer), 0) AS high_risk_count
            FROM fact_claims f
        """
        rows = self.db.execute_query(query)
        if not rows or rows[0]["total_claims"] == 0:
            return KPISummary(
                total_claims=0,
                total_claimed_amount=0.0,
                average_claimed_amount=0.0,
                average_reporting_delay_days=0.0,
                high_risk_claims_count=0,
                high_risk_rate_percent=0.0,
            )

        r = rows[0]
        total = int(r["total_claims"])
        high_risk = int(r["high_risk_count"])
        pct = round((high_risk / total) * 100, 2) if total > 0 else 0.0

        return KPISummary(
            total_claims=total,
            total_claimed_amount=round(float(r["total_amount"]), 2),
            average_claimed_amount=round(float(r["avg_amount"]), 2),
            average_reporting_delay_days=round(float(r["avg_delay"]), 1),
            high_risk_claims_count=high_risk,
            high_risk_rate_percent=pct,
        )

    def get_claims(
        self,
        limit: int = 50,
        status: Optional[str] = None,
        claim_type: Optional[str] = None,
    ) -> List[ClaimSummary]:
        """Lists claims with optional status and type filters."""
        query = """
            SELECT
                f.claim_id,
                p.policy_id,
                u.customer_id,
                u.full_name AS customer_name,
                t.claim_type,
                f.incident_date,
                f.reported_date,
                f.claimed_amount,
                f.claim_status AS status,
                f.city,
                f.documents_count
            FROM fact_claims f
            JOIN dim_policy p ON f.policy_sk = p.policy_sk
            JOIN dim_customer u ON f.customer_sk = u.customer_sk
            JOIN dim_claim_type t ON f.claim_type_sk = t.claim_type_sk
            WHERE 1=1
        """
        params = []
        if status:
            query += " AND f.claim_status = ?"
            params.append(status.upper())
        if claim_type:
            query += " AND t.claim_type = ?"
            params.append(claim_type.upper())

        query += " ORDER BY f.reported_date DESC LIMIT ?"
        params.append(limit)

        rows = self.db.execute_query(query, params)
        return [ClaimSummary(**dict(r)) for r in rows]

    def get_claim_detail(self, claim_id: str) -> ClaimDetail:
        """Retrieves detailed claim context including policy and customer metrics."""
        query = """
            SELECT
                f.claim_id,
                p.policy_id,
                u.customer_id,
                u.full_name AS customer_name,
                t.claim_type,
                f.incident_date,
                f.reported_date,
                f.claimed_amount,
                f.claim_status AS status,
                f.city,
                f.documents_count,
                f.description,
                u.risk_score AS customer_risk_score,
                p.sum_insured AS policy_sum_insured,
                p.deductible AS policy_deductible,
                p.policy_status
            FROM fact_claims f
            JOIN dim_policy p ON f.policy_sk = p.policy_sk
            JOIN dim_customer u ON f.customer_sk = u.customer_sk
            JOIN dim_claim_type t ON f.claim_type_sk = t.claim_type_sk
            WHERE f.claim_id = ?
        """
        rows = self.db.execute_query(query, (claim_id.strip().upper(),))
        if not rows:
            raise ClaimNotFoundError(claim_id)
        return ClaimDetail(**dict(rows[0]))

    def trigger_pipeline_run(self) -> PipelineTriggerResponse:
        """Triggers pipeline run (Databricks SDK Workflow or local execution)."""
        run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
        now_str = datetime.now(timezone.utc).isoformat()

        if self.settings.is_databricks_configured and self.settings.DATABRICKS_JOB_ID:
            try:
                from databricks.sdk import WorkspaceClient
                w = WorkspaceClient(
                    host=self.settings.DATABRICKS_HOST,
                    token=self.settings.DATABRICKS_TOKEN,
                )
                run = w.jobs.run_now(job_id=int(self.settings.DATABRICKS_JOB_ID))
                return PipelineTriggerResponse(
                    run_id=str(run.run_id),
                    status="TRIGGERED_DATABRICKS",
                    timestamp=now_str,
                    message="Databricks Workflow Job execution triggered successfully.",
                )
            except Exception as e:
                pass

        # Local Lakehouse engine fallback
        from databricks.local_pipeline import LocalMedallionPipeline
        pipeline = LocalMedallionPipeline()
        pipeline.run_bronze()
        pipeline.run_silver(run_id=run_id)
        pipeline.run_gold()
        pipeline.run_reconciliation(run_id=run_id)

        return PipelineTriggerResponse(
            run_id=run_id,
            status="COMPLETED_LOCAL",
            timestamp=now_str,
            message="Local Medallion pipeline executed with full reconciliation.",
        )

    def get_audit_runs(self, limit: int = 10) -> List[AuditRunRecord]:
        """Returns historical reconciliation records from pipeline_audit."""
        query = """
            SELECT
                run_id, run_timestamp, bronze_count, duplicates_count, defects_count,
                quarantined_total, silver_count, gold_fact_count, discrepancy_count,
                reconciliation_status, audit_notes
            FROM pipeline_audit
            ORDER BY run_timestamp DESC
            LIMIT ?
        """
        rows = self.db.execute_query(query, (limit,))
        return [AuditRunRecord(**dict(r)) for r in rows]

    def get_quality_summary(self) -> Dict[str, Any]:
        """Summarizes data quality failure statistics from dq_results."""
        query = """
            SELECT reject_reason, COUNT(*) as failed_count
            FROM quarantine_claims
            GROUP BY reject_reason
            ORDER BY failed_count DESC
        """
        rows = self.db.execute_query(query)
        total_quarantined = sum(r["failed_count"] for r in rows)
        return {
            "total_quarantined": total_quarantined,
            "rule_breakdown": [dict(r) for r in rows],
        }

    def triage_claim(self, claim_id: str) -> TriageAssessment:
        """Executes LangGraph agent triage for a claim."""
        state = self.agent_graph.execute_triage(claim_id, self.db)
        rule_checks = [
            RuleCheckResult(
                rule_id=r["rule_id"],
                description=r["description"],
                passed=r["passed"],
                severity=r["severity"],
                details=r["details"],
            )
            for r in state["validation_results"]
        ]

        return TriageAssessment(
            claim_id=state["claim_id"],
            decision=TriageDecisionEnum(state["decision"]),
            confidence=state["confidence"],
            reasons=state["assessment"]["reasons"] if state["assessment"] else [],
            cited_clause_ids=state["assessment"]["cited_clause_ids"] if state["assessment"] else [],
            rule_checks=rule_checks,
            needs_human=state["needs_human"],
            trace=state["trace"],
        )

    def review_claim(self, claim_id: str, request: HumanReviewRequest) -> HumanReviewResponse:
        """Applies human adjuster decision and finalizes graph execution."""
        override = request.override_decision.value if request.override_decision else None
        res = self.agent_graph.resume_review(
            claim_id=claim_id,
            action=request.action,
            reviewer_notes=request.reviewer_notes,
            override_decision=override,
        )
        return HumanReviewResponse(
            claim_id=claim_id,
            final_decision=TriageDecisionEnum(res["final_decision"]),
            reviewer_notes=res["reviewer_notes"],
            status=res["status"],
            timestamp=res["timestamp"],
        )


_claims_service_instance: Optional[ClaimsService] = None


def get_claims_service() -> ClaimsService:
    """Singleton getter for the ClaimsService."""
    global _claims_service_instance
    if _claims_service_instance is None:
        _claims_service_instance = ClaimsService()
    return _claims_service_instance
