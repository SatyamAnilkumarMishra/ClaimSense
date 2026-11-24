"""FastAPI REST Application for ClaimSense.

Provides secure REST endpoints for claims intelligence, pipeline triggering,
and LangGraph triage agent execution.

Security:
- Header-based API Key Authentication (`X-API-Key`) with constant-time comparison
- Rate limiting per client IP using SlowAPI
- Strict CORS allow-listing
- Generic error handling preventing stack trace leakage
"""

from __future__ import annotations

import logging
import secrets
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from claimsense.config import get_settings
from claimsense.db.errors import ClaimNotFoundError
from claimsense.services.claims_service import get_claims_service
from claimsense.services.models import (
    AuditRunRecord,
    ClaimDetail,
    ClaimSummary,
    HumanReviewRequest,
    HumanReviewResponse,
    KPISummary,
    PipelineTriggerResponse,
    SystemHealthResponse,
    TriageAssessment,
)

logger = logging.getLogger("claimsense.api")
settings = get_settings()

# Rate Limiter setup
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

app = FastAPI(
    title="ClaimSense Lakehouse & AI Triage API",
    description="REST API for Insurance Lakehouse analytics, Databricks pipeline execution, and LangGraph agent triage.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Middleware (Restricted to Streamlit application origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# Security: API Key Dependency (Constant-Time Verification)
def verify_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")) -> str:
    """Enforces constant-time API key verification for protected endpoints."""
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.FASTAPI_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key


# Global Exception Handler (Shields Internal Traces)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = uuid.uuid4().hex[:8]
    logger.error(f"Unhandled exception [Request ID: {req_id}]: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred while processing your request.",
            "request_id": req_id,
        },
    )


# -----------------------------------------------------------------------------
# REST Endpoints
# -----------------------------------------------------------------------------


@app.get("/health", response_model=SystemHealthResponse, tags=["System"])
def health_check():
    """Returns connectivity and operational status across Databricks, Groq, and fallback modes."""
    service = get_claims_service()
    return service.get_health()


@app.get("/kpis", response_model=KPISummary, tags=["Analytics"])
def get_kpis():
    """Returns aggregated claim counts, amounts, reporting delays, and risk rates."""
    service = get_claims_service()
    return service.get_kpi_summary()


@app.get("/claims", response_model=list[ClaimSummary], tags=["Claims"])
def list_claims(
    limit: int = Query(default=50, ge=1, le=500),
    status: str | None = Query(default=None),
    claim_type: str | None = Query(default=None),
):
    """Retrieves claim records with optional filters."""
    service = get_claims_service()
    return service.get_claims(limit=limit, status=status, claim_type=claim_type)


@app.get("/claims/{claim_id}", response_model=ClaimDetail, tags=["Claims"])
def get_claim(claim_id: str):
    """Retrieves single claim detail including policy and customer metrics."""
    service = get_claims_service()
    try:
        return service.get_claim_detail(claim_id)
    except ClaimNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Claim '{claim_id}' not found."
        ) from err


@app.post(
    "/pipeline/run",
    response_model=PipelineTriggerResponse,
    dependencies=[Depends(verify_api_key)],
    tags=["Pipeline"],
)
@limiter.limit("5/minute")
def trigger_pipeline(request: Request):
    """Triggers end-to-end pipeline execution with rate limiting and API key auth."""
    service = get_claims_service()
    return service.trigger_pipeline_run()


@app.get("/pipeline/status/{run_id}", tags=["Pipeline"])
def get_pipeline_status(run_id: str):
    """Returns execution status for a specific pipeline run."""
    service = get_claims_service()
    runs = service.get_audit_runs(limit=10)
    matching = next((r for r in runs if r.run_id == run_id), None)
    if not matching:
        return {"run_id": run_id, "status": "UNKNOWN_OR_IN_PROGRESS"}
    return matching


@app.get("/audit/runs", response_model=list[AuditRunRecord], tags=["Audit"])
def get_audit_history(limit: int = Query(default=10, ge=1, le=50)):
    """Returns reconciliation history records from pipeline_audit."""
    service = get_claims_service()
    return service.get_audit_runs(limit=limit)


@app.get("/quality/summary", tags=["Quality"])
def get_quality_summary():
    """Returns quarantine breakdown and data quality rule violations."""
    service = get_claims_service()
    return service.get_quality_summary()


@app.post(
    "/triage/{claim_id}",
    response_model=TriageAssessment,
    dependencies=[Depends(verify_api_key)],
    tags=["AI Triage"],
)
@limiter.limit("30/minute")
def triage_claim(request: Request, claim_id: str):
    """Executes the LangGraph StateGraph triage agent with anti-hallucination citations."""
    service = get_claims_service()
    try:
        return service.triage_claim(claim_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except ClaimNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Claim '{claim_id}' not found."
        ) from err


@app.post(
    "/triage/{claim_id}/review",
    response_model=HumanReviewResponse,
    dependencies=[Depends(verify_api_key)],
    tags=["AI Triage"],
)
@limiter.limit("30/minute")
def human_review_claim(
    request: Request,
    claim_id: str,
    review_req: HumanReviewRequest,
):
    """Resumes the LangGraph agent after human adjuster review (approve, override, or reject)."""
    service = get_claims_service()
    try:
        return service.review_claim(claim_id, review_req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
