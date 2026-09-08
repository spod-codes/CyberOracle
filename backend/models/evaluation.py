from typing import Any

from pydantic import BaseModel, Field

class MitrePrediction(BaseModel):
    rank: int
    class_id: int
    stage: str
    technique_id: str
    technique_name: str
    confidence: float


class TimelinePoint(BaseModel):
    label: str
    probability: float
    kind: str
    stage: str


class StagePoint(BaseModel):
    name: str
    short_name: str
    probability: float
    status: str
    tactic: str


class FeatureAttribution(BaseModel):
    feature: str
    value: str
    weight: float
    direction: str
    explanation: str


class FlowAlert(BaseModel):
    id: str
    timestamp: str
    source: str
    destination: str
    protocol: str
    flags: str
    risk: float
    severity: str
    stage: str
    signal: str


class BenchmarkMetrics(BaseModel):
    world_model: dict[str, float]
    logistic_baseline: dict[str, float]
    lift: dict[str, float]
    source: str
    labelled_rows: int


class ReplayNoteCreate(BaseModel):
    window_label: str = Field(min_length=1, max_length=32)
    text: str = Field(min_length=1, max_length=400)
    category: str = Field(default="Finding", min_length=1, max_length=40)


class ReplayNoteUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=400)
    category: str = Field(min_length=1, max_length=40)


class ReplayNote(BaseModel):
    id: str
    window_label: str
    text: str
    category: str = "Finding"
    created_at: str
    updated_at: str | None = None


class BriefingSignoffUpdate(BaseModel):
    analyst_name: str = Field(max_length=100)
    status: str = Field(max_length=32)
    approval_date: str | None = None


class BriefingSignoff(BaseModel):
    analyst_name: str = ""
    status: str = "Draft"
    approval_date: str | None = None
    updated_at: str | None = None


class EvaluationRecord(BaseModel):
    id: str
    filename: str
    created_at: str
    rows: int
    features: int
    flow_features: list[str]
    packet_features: list[str]
    headers: list[str]
    preview: list[dict[str, Any]]
    window_size: int
    architecture: str
    horizon: int
    explainability: str
    current_stage: str
    forecast_stage: str
    risk_score: float
    forecast_probability: float
    lead_windows: float
    timeline: list[TimelinePoint]
    stages: list[StagePoint]
    attributions: list[FeatureAttribution]
    flows: list[FlowAlert]
    benchmark: BenchmarkMetrics
    context_multiplier: float = 1.0
    notes: list[ReplayNote] = Field(default_factory=list)
    signoff: BriefingSignoff = Field(default_factory=BriefingSignoff)
    model_status: str = "offline-deterministic"
    mitre_predictions: list[MitrePrediction] = []
    forecast_method: str = "ar1"
    shap_computed: bool = False
    attention_weights: list[float] | None = None


class EvaluationListItem(BaseModel):
    id: str
    filename: str
    created_at: str
    rows: int
    risk_score: float
    current_stage: str
    forecast_stage: str
    architecture: str


class DeleteResponse(BaseModel):
    deleted: bool = Field(default=True)


class KernelTestResult(BaseModel):
    status: str
    logs: list[str]
    checks: dict[str, bool]
    metrics: dict[str, float]
    duration_ms: int
    tested_at: str