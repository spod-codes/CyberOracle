import asyncio
import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import joblib
import numpy as np
import psutil
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse

from lib.agent_script import build_agent_script
from lib.calibration import MIN_EVIDENCE_EVENTS, proposal_value
from lib.db import db
from models.supervision import AgentCreate, AgentEnrollment, AgentSummary, IngestResponse, ModelContext, ModelProposal, PacketEvent, PacketMetadataInput, ProposalDecision, SupervisionSummary

router = APIRouter(prefix="/supervision", tags=["supervision"])
RETENTION_DAYS = 7

# Load the trained RandomForest model once at startup for live packet scoring
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "cic_ids_model.pkl")
try:
    _clf = joblib.load(_MODEL_PATH)
    print(f"[Supervision] Loaded ML model from {_MODEL_PATH}")
except Exception as _e:
    _clf = None
    print(f"[Supervision] WARNING: Could not load ML model ({_e}). Falling back to heuristic scoring.")

# local capture moved to live.py


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    await db.supervision_agents.delete_one({"id": agent_id})
    await db.supervision_events.delete_many({"agent_id": agent_id})
    return {"status": "deleted"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _risk(event: PacketMetadataInput, multiplier: float) -> float:
    """Score a single live packet event using the trained RandomForest model.
    
    We build the same 9-feature vector that train.py used:
    [duration, fwd_pkts, fwd_bytes, iat_mean, ttl, src_port, dst_port, pkt_size, flag_count]
    """
    if _clf is not None:
        try:
            flags = event.tcp_flags.upper() if event.tcp_flags else ""
            flag_count = sum(f in flags for f in ("SYN", "ACK", "PSH", "RST", "URG", "FIN"))
            # Build feature vector matching the training schema
            X = np.array([[
                1000.0,                           # flow_duration (placeholder, 1 packet)
                1,                                # total_fwd_packets
                float(event.packet_size),         # total_length_fwd_packets
                500.0,                            # flow_iat_mean (placeholder)
                64.0,                             # ttl_mean (placeholder)
                float(event.source_port or 0),    # src_port
                float(event.destination_port or 0), # dst_port
                float(event.packet_size),         # packet_size
                float(flag_count),                # tcp_flag_count
            ]], dtype=np.float64)
            X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
            prob = float(_clf.predict_proba(X)[0, 1])
            return round(max(0.0, min(1.0, prob * multiplier)), 3)
        except Exception:
            pass  # Fall through to heuristic

    # Fallback heuristic when model unavailable
    score = 0.08
    flags = event.tcp_flags.upper() if event.tcp_flags else ""
    score += min(0.28, sum(flag in flags for flag in ("SYN", "RST", "PSH", "URG")) * 0.07)
    if event.destination_port is not None and event.destination_port < 1024:
        score += 0.12
    if event.packet_size >= 32_000:
        score += 0.14
    elif event.packet_size >= 8_000:
        score += 0.07
    return round(max(0.0, min(1.0, score * multiplier)), 3)



def _severity(risk: float) -> str:
    return "Critical" if risk >= 0.82 else "High" if risk >= 0.62 else "Medium" if risk >= 0.38 else "Low"


async def _context() -> ModelContext:
    document = await db.model_context.find_one({"id": "active"})
    return ModelContext(**document) if document else ModelContext()


async def _maybe_propose(*, force: bool = False) -> None:
    if await db.model_proposals.find_one({"status": "Pending"}):
        return
    events = await db.supervision_events.find({}, {"risk": 1}).sort("received_at", -1).to_list(200)
    if len(events) < MIN_EVIDENCE_EVENTS:
        return
    average = sum(float(event.get("risk", 0)) for event in events) / len(events)
    context = await _context()
    proposed = proposal_value(average, context.risk_multiplier, force=force)
    if proposed is None:
        return
    proposal = ModelProposal(id=str(uuid4()), title="Calibrate live risk sensitivity", rationale=f"Recent server traffic averaged {average:.1%} risk across {len(events)} metadata events.", parameter="risk_multiplier", current_value=context.risk_multiplier, proposed_value=proposed, status="Pending", evidence_events=len(events), created_at=_now().isoformat())
    await db.model_proposals.insert_one(proposal.model_dump())


@router.post("/agents", response_model=AgentEnrollment)
async def create_agent(input: AgentCreate):
    token = secrets.token_urlsafe(32)
    agent_id = str(uuid4())
    created_at = _now().isoformat()
    await db.supervision_agents.insert_one({"id": agent_id, "name": input.name.strip(), "token_hash": hashlib.sha256(token.encode()).hexdigest(), "created_at": created_at, "last_seen": None, "packets_ingested": 0})
    return AgentEnrollment(id=agent_id, name=input.name.strip(), token=token, created_at=created_at, download_path=f"/api/supervision/agents/{agent_id}/download")


@router.get("/agents", response_model=list[AgentSummary])
async def list_agents():
    documents = await db.supervision_agents.find({}, {"_id": 0, "token_hash": 0}).sort("created_at", -1).to_list(50)
    now = _now()
    return [AgentSummary(**document, status="Live" if document.get("last_seen") and now - datetime.fromisoformat(document["last_seen"]) < timedelta(seconds=30) else "Offline") for document in documents]


@router.get("/agents/{agent_id}/download", response_class=PlainTextResponse)
async def download_agent(agent_id: str, token: str = Query(...), base_url: str = Query(...)):
    document = await db.supervision_agents.find_one({"id": agent_id, "token_hash": hashlib.sha256(token.encode()).hexdigest()})
    if not document:
        raise HTTPException(status_code=404, detail="Agent enrollment not found.")
    if not base_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="A valid Cyber Oracle URL is required.")
    response = PlainTextResponse(build_agent_script(base_url.rstrip("/"), token, agent_id))
    response.headers["Content-Disposition"] = 'attachment; filename="cyber_oracle_agent.py"'
    return response


@router.post("/ingest", response_model=IngestResponse)
async def ingest_metadata(events: list[PacketMetadataInput], x_agent_token: str = Header(...)):
    if not events or len(events) > 500:
        raise HTTPException(status_code=422, detail="Send between 1 and 500 metadata events per batch.")
    token_hash = hashlib.sha256(x_agent_token.encode()).hexdigest()
    agent = await db.supervision_agents.find_one({"token_hash": token_hash})
    if not agent:
        raise HTTPException(status_code=401, detail="Unknown supervision agent.")
    context = await _context()
    received = _now()
    documents = []
    for event in events:
        risk = _risk(event, context.risk_multiplier)
        documents.append({**event.model_dump(), "id": str(uuid4()), "agent_id": agent["id"], "received_at": received.isoformat(), "expires_at": received + timedelta(days=RETENTION_DAYS), "risk": risk, "severity": _severity(risk)})
    await db.supervision_events.insert_many(documents)
    await db.supervision_agents.update_one({"id": agent["id"]}, {"$set": {"last_seen": received.isoformat()}, "$inc": {"packets_ingested": len(documents)}})
    await _maybe_propose()
    return IngestResponse(accepted=len(documents))


@router.get("/summary", response_model=SupervisionSummary)
async def get_summary():
    cutoff = (_now() - timedelta(hours=24)).isoformat()
    events = await db.supervision_events.find({"received_at": {"$gte": cutoff}}, {"_id": 0, "expires_at": 0}).sort("received_at", -1).to_list(500)
    agents = await list_agents()
    totals = await db.supervision_events.aggregate([
        {"$match": {"received_at": {"$gte": cutoff}}},
        {"$group": {"_id": None, "packets": {"$sum": 1}, "bytes": {"$sum": "$packet_size"}, "high_risk": {"$sum": {"$cond": [{"$gte": ["$risk", 0.62]}, 1, 0]}}}},
    ]).to_list(1)
    protocol_rows = await db.supervision_events.aggregate([
        {"$match": {"received_at": {"$gte": cutoff}}},
        {"$group": {"_id": "$protocol", "count": {"$sum": 1}}},
    ]).to_list(50)
    total = totals[0] if totals else {"packets": 0, "bytes": 0, "high_risk": 0}
    return SupervisionSummary(active_agents=sum(agent.status == "Live" for agent in agents), total_agents=len(agents), packets_24h=total["packets"], bytes_24h=total["bytes"], high_risk_24h=total["high_risk"], protocol_counts={row["_id"]: row["count"] for row in protocol_rows}, recent_events=[PacketEvent(**event) for event in events[:100]])


@router.get("/context", response_model=ModelContext)
async def get_context():
    return await _context()


@router.get("/proposals", response_model=list[ModelProposal])
async def list_proposals():
    return [ModelProposal(**document) for document in await db.model_proposals.find({}, {"_id": 0}).sort("created_at", -1).to_list(20)]


@router.post("/proposals/generate", response_model=list[ModelProposal])
async def generate_proposal():
    await _maybe_propose(force=True)
    return await list_proposals()


@router.post("/proposals/{proposal_id}/decision", response_model=ModelProposal)
async def decide_proposal(proposal_id: str, input: ProposalDecision):
    document = await db.model_proposals.find_one({"id": proposal_id})
    if not document:
        raise HTTPException(status_code=404, detail="Model proposal not found.")
    status = "Approved" if input.approved else "Rejected"
    decided_at = _now().isoformat()
    await db.model_proposals.update_one({"id": proposal_id}, {"$set": {"status": status, "decided_at": decided_at}})
    if input.approved:
        await db.model_context.update_one({"id": "active"}, {"$set": {"risk_multiplier": document["proposed_value"], "updated_at": decided_at, "source_proposal_id": proposal_id}}, upsert=True)
    return ModelProposal(**{**document, "status": status, "decided_at": decided_at})