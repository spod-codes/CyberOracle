from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class AgentEnrollment(BaseModel):
    id: str
    name: str
    token: str
    created_at: str
    download_path: str


class AgentSummary(BaseModel):
    id: str
    name: str
    status: str
    created_at: str
    last_seen: str | None = None
    packets_ingested: int = 0


class PacketMetadataInput(BaseModel):
    timestamp: str
    interface: str
    source: str
    destination: str
    source_port: int | None = None
    destination_port: int | None = None
    protocol: str
    tcp_flags: str = ""
    packet_size: int
    ttl: int | None = None


class PacketEvent(PacketMetadataInput):
    id: str
    agent_id: str
    received_at: str
    risk: float
    severity: str


class SupervisionSummary(BaseModel):
    active_agents: int
    total_agents: int
    packets_24h: int
    bytes_24h: int
    high_risk_24h: int
    protocol_counts: dict[str, int]
    recent_events: list[PacketEvent]
    retention_days: int = 7
    capture_mode: str = "agent-packet-metadata"


class ModelProposal(BaseModel):
    id: str
    title: str
    rationale: str
    parameter: str
    current_value: float
    proposed_value: float
    status: str
    evidence_events: int
    created_at: str
    decided_at: str | None = None


class ProposalDecision(BaseModel):
    approved: bool


class ModelContext(BaseModel):
    risk_multiplier: float = 1.0
    updated_at: str | None = None
    source_proposal_id: str | None = None


class IngestResponse(BaseModel):
    accepted: int
    retention_days: int = 7