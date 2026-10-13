"""
FastAPI REST API Server for Hl7 Mirth Auditor.
"""
from typing import Dict, Any, List, Optional
import json
import os
import secrets
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from .base import AuditLogger, PHIGuard, SecurityException
from .models import SystemTaskPayload, ConsensusDossier
from .supervisor import SystemSupervisor

supervisor = SystemSupervisor(model_provider="mock")

app = FastAPI(
    title="Hl7 Mirth Auditor API",
    description="Enterprise Distributed Component Platform (Clinical & Biomedical AI)",
    version="3.0.0-ENTERPRISE",
)


class ChatRequest(BaseModel):
    query: str


def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    """Protect API operations when an access key is configured."""
    configured = os.environ.get("AUDITOR_API_KEY")
    if configured and (not x_api_key or not secrets.compare_digest(x_api_key, configured)):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.exception_handler(SecurityException)
async def security_exception_handler(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=422, content={"detail": "Potential sensitive identifier in input"})


@app.get("/health")
def health():
    return {"status": "HEALTHY", "service": "hl7-mirth-auditor", "domain": "Clinical & Biomedical AI", "standard": "CAP / CLSI / ISO Standards", "version": "3.0.0-ENTERPRISE"}


@app.get("/metrics")
def metrics(_auth=Depends(require_api_key)):
    return {
        "dossiers_processed_total": len(supervisor.dossier_registry),
        "audit_blocks_total": len(AuditLogger.get_trail()),
        "system_status": "NOMINAL_OPTIMAL"
    }


@app.post("/api/audit")
def api_audit(payload: SystemTaskPayload, _auth=Depends(require_api_key)):
    PHIGuard.assert_no_phi(json.dumps(payload.attributes, ensure_ascii=False))
    dossier = supervisor.process_task(payload)
    return dossier.to_dict()


@app.post("/api/chat")
def api_chat(req: ChatRequest, _auth=Depends(require_api_key)):
    try:
        ans = supervisor.query_supervisory_chat(req.query)
        return {"response": ans}
    except SecurityException:
        raise HTTPException(status_code=422, detail="Potential sensitive identifier in input")
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to process the chat request")


@app.get("/api/audit/logs")
def api_audit_logs(_auth=Depends(require_api_key)):
    return {"audit_trail": AuditLogger.get_trail(), "verified": AuditLogger.verify_integrity()}
