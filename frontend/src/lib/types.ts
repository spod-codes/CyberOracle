export interface MitrePrediction {
  rank: number;
  class_id: number;
  stage: string;
  technique_id: string;
  technique_name: string;
  confidence: number;
}

export interface TimelinePoint {
  label: string;
  probability: number;
  kind: string;
  stage: string;
}

export interface StagePoint {
  name: string;
  short_name: string;
  probability: number;
  status: string;
  tactic: string;
}

export interface FeatureAttribution {
  feature: string;
  value: string;
  weight: number;
  direction: string;
  explanation: string;
}

export interface FlowAlert {
  id: string;
  timestamp: string;
  source: string;
  destination: string;
  protocol: string;
  flags: string;
  risk: number;
  severity: string;
  stage: string;
  signal: string;
}

export interface BenchmarkMetrics {
  world_model: Record<string, number>;
  logistic_baseline: Record<string, number>;
  lift: Record<string, number>;
    source: string;
    labelled_rows: number;
}

export interface ReplayNote {
  id: string;
  window_label: string;
  text: string;
  category: string;
  created_at: string;
  updated_at: string | null;
}

export interface ReplayNoteCreate {
  window_label: string;
  text: string;
  category: string;
}

export interface ReplayNoteUpdate {
  text: string;
  category: string;
}

export interface BriefingSignoff {
  analyst_name: string;
  status: string;
  approval_date: string | null;
  updated_at: string | null;
}

export interface BriefingSignoffUpdate {
  analyst_name: string;
  status: string;
  approval_date: string | null;
}

export interface EvaluationRecord {
  id: string;
  filename: string;
  created_at: string;
  rows: number;
  features: number;
  flow_features: string[];
  packet_features: string[];
  headers: string[];
  preview: Array<Record<string, string | number | null>>;
  window_size: number;
  architecture: string;
  horizon: number;
  explainability: string;
  current_stage: string;
  forecast_stage: string;
  risk_score: number;
  forecast_probability: number;
  lead_windows: number;
  timeline: TimelinePoint[];
  stages: StagePoint[];
  attributions: FeatureAttribution[];
  flows: FlowAlert[];
  benchmark: BenchmarkMetrics;
  context_multiplier: number;
  notes: ReplayNote[];
  signoff: BriefingSignoff;
  model_status: string;
  mitre_predictions?: MitrePrediction[];
  forecast_method?: string;
  shap_computed?: boolean;
  attention_weights?: number[] | null;
}

export interface DeleteResponse {
  deleted: boolean;
}

export interface KernelTestResult {
  status: string;
  logs: string[];
  checks: Record<string, boolean>;
  metrics: Record<string, number>;
  duration_ms: number;
  tested_at: string;
}

export interface AgentEnrollment { id: string; name: string; token: string; created_at: string; download_path: string; }
export interface AgentCreate { name: string; }
export interface AgentSummary { id: string; name: string; status: string; created_at: string; last_seen: string | null; packets_ingested: number; }
export interface PacketMetadataInput { timestamp: string; interface: string; source: string; destination: string; source_port: number | null; destination_port: number | null; protocol: string; tcp_flags: string; packet_size: number; ttl: number | null; }
export interface PacketEvent { id: string; agent_id: string; timestamp: string; interface: string; source: string; destination: string; source_port: number | null; destination_port: number | null; protocol: string; tcp_flags: string; packet_size: number; ttl: number | null; received_at: string; risk: number; severity: string; features?: Record<string, number>; is_simulation?: boolean; pattern_risk?: number; }
export interface SupervisionSummary { active_agents: number; total_agents: number; packets_24h: number; bytes_24h: number; high_risk_24h: number; protocol_counts: Record<string, number>; recent_events: PacketEvent[]; retention_days: number; capture_mode: string; }
export interface ModelProposal { id: string; title: string; rationale: string; parameter: string; current_value: number; proposed_value: number; status: string; evidence_events: number; created_at: string; decided_at: string | null; }
export interface ModelContext { risk_multiplier: number; updated_at: string | null; source_proposal_id: string | null; }
export interface ProposalDecision { approved: boolean; }
export interface IngestResponse { accepted: number; retention_days: number; }

export interface EvaluationListItem {
  id: string;
  filename: string;
  created_at: string;
  rows: number;
  risk_score: number;
  current_stage: string;
  forecast_stage: string;
  architecture: string;
}