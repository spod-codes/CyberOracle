import { useMemo, useState } from "react";
import type { ChangeEvent, CSSProperties, DragEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, ChevronRight, Clock3, FileSpreadsheet, FileUp, Play, RefreshCw, UploadCloud } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import AppHeader from "@/components/AppHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiGet, apiUpload, ApiError } from "@/lib/api";
import type { EvaluationListItem, EvaluationRecord } from "@/lib/types";

const THREAT_ART_URL = "/threat-identity.png";


interface DatasetInspection {
  rows: number;
  headers: string[];
  flowFeatures: string[];
  packetFeatures: string[];
}

function parseCsvHeader(line: string): string[] {
  const fields: string[] = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    if (character === '"' && line[index + 1] === '"') { current += '"'; index += 1; }
    else if (character === '"') quoted = !quoted;
    else if (character === "," && !quoted) { fields.push(current.trim()); current = ""; }
    else current += character;
  }
  fields.push(current.trim());
  return fields.filter(Boolean);
}

function inspectCsv(content: string): DatasetInspection {
  const lines = content.replace(/^\uFEFF/, "").split(/\r?\n/).filter((line) => line.trim());
  const headers = parseCsvHeader(lines[0] ?? "");
  const flowTerms = ["ip", "port", "protocol", "flag", "byte", "packet", "duration", "flow"];
  const packetTerms = ["ttl", "window", "fragment", "payload", "iat", "retrans", "scan"];
  return {
    rows: Math.max(0, lines.length - 1),
    headers,
    flowFeatures: headers.filter((header) => flowTerms.some((term) => header.toLowerCase().includes(term))),
    packetFeatures: headers.filter((header) => packetTerms.some((term) => header.toLowerCase().includes(term))),
  };
}

function formatError(error: unknown): string {
  if (error instanceof ApiError && typeof error.body === "object" && error.body !== null && "detail" in error.body) {
    return String(error.body.detail);
  }
  return "The local inference runtime could not evaluate this file.";
}

export default function Home() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [architecture, setArchitecture] = useState("Temporal Transformer");
  const [horizon, setHorizon] = useState("8");
  const [windowSize, setWindowSize] = useState("50");
  const [explainability, setExplainability] = useState("Attention weights");
  const [inspection, setInspection] = useState<DatasetInspection | null>(null);
  const evaluations = useQuery({ queryKey: ["evaluations"], queryFn: () => apiGet<EvaluationListItem[]>("/evaluations"), retry: false });
  const runMutation = useMutation({
    mutationFn: async (selectedFile: File) => {
      const form = new FormData();
      form.append("file", selectedFile);
      form.append("architecture", architecture);
      form.append("horizon", horizon);
      form.append("window_size", windowSize);
      form.append("explainability", explainability);
      return apiUpload<EvaluationRecord>("/evaluations", form);
    },
    onSuccess: (result) => {
      toast.success("Trajectory evaluation complete", { description: "Opening your predictive command center." });
      navigate(`/dashboard/${result.id}`);
    },
  });

  const fileSummary = useMemo(() => {
    if (!file) return "Awaiting telemetry file";
    return `${file.name} · ${(file.size / 1024).toFixed(1)} KB ready`;
  }, [file]);
  const detectedWindows = inspection ? Math.max(1, inspection.rows <= Number(windowSize) ? inspection.rows : Math.ceil(inspection.rows / Number(windowSize))) : 0;

  const selectFile = async (selected: File | undefined) => {
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith(".csv")) {
      toast.error("CSV format required", { description: "Upload a flow or packet telemetry CSV." });
      return;
    }
    const parsed = inspectCsv(await selected.text());
    if (!parsed.headers.length) {
      setFile(null);
      setInspection(null);
      toast.error("Header row not found", { description: "Choose a CSV with named telemetry columns." });
      return;
    }
    setFile(selected);
    setInspection(parsed);
    toast.success("Telemetry staged", { description: `${selected.name} is ready for local evaluation.` });
  };

  const handleInput = (event: ChangeEvent<HTMLInputElement>) => void selectFile(event.target.files?.[0]);
  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragging(false);
    void selectFile(event.dataTransfer.files[0]);
  };
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: () => apiGet<{id: string, name: string, size: number}[]>("/evaluations/datasets") });

  const loadSample = async (id: string, name: string) => {
    toast.info("Downloading dataset...", { description: name });
    const baseUrl = import.meta.env.VITE_API_URL || "/api";
    try {
      const res = await fetch(`${baseUrl}/evaluations/datasets/${id}`, {
        headers: { "Bypass-Tunnel-Reminder": "true" }
      });
      const blob = await res.blob();
      const sampleFile = new File([blob], name, { type: "text/csv" });
      const parsed = inspectCsv(await sampleFile.text());
      setFile(sampleFile);
      setInspection(parsed);
      toast.success("Dataset loaded", { description: `${name} is ready.` });
    } catch (err) {
      toast.error("Failed to load dataset");
    }
  };

  return (
    <div className="app-shell" data-testid="ingestion-page">
      <AppHeader />
      <main className="ingest-main">
        <section className="ingest-hero" data-testid="ingestion-hero" style={{ display: "flex", position: "relative", overflow: "hidden", minHeight: "500px", background: "var(--background)", color: "var(--foreground)", marginBottom: "40px", borderRadius: "16px", border: "2px solid var(--border)", boxShadow: "0 20px 40px rgba(0,0,0,0.1)" }}>
          <div style={{ flex: 1, padding: "60px", position: "relative", zIndex: 2, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
            <div>
              <div style={{ display: "flex", gap: "40px", fontSize: "10px", textTransform: "uppercase", letterSpacing: "1px", fontWeight: "bold", opacity: 0.6, marginBottom: "80px" }}>
                <span>WORLD MODEL</span>
                <span>The system ingests network traffic, learns temporal behaviour, and forecasts future attack states.</span>
              </div>
              <h1 style={{ fontSize: "clamp(80px, 12vw, 160px)", fontWeight: 900, letterSpacing: "-0.05em", lineHeight: 0.8, margin: 0, color: "var(--foreground)" }}>oracle.</h1>
            </div>
            <div style={{ position: "relative", height: "120px" }}>
              <div style={{ position: "absolute", bottom: "-20px", left: "-20px", transform: "rotate(-90deg)", transformOrigin: "left bottom", fontSize: "clamp(60px, 10vw, 120px)", fontWeight: 900, color: "var(--foreground)", opacity: 0.05 }}>001</div>
            </div>
          </div>
          <div style={{ flex: 1, position: "relative", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", width: "120%", height: "250px", background: "#ff4d30", zIndex: 0 }}></div>
            <img src={THREAT_ART_URL} alt="" style={{ position: "relative", zIndex: 1, height: "400px", objectFit: "cover", mixBlendMode: "luminosity", opacity: 0.9 }} />
          </div>
        </section>

        <section className="ingest-grid" data-testid="ingestion-workspace">
          <div className="ingest-column">
            <div className="section-kicker" title="Upload network traffic records for analysis."><span>01</span> INGEST TELEMETRY</div>
            <label className={`dropzone ${dragging ? "dropzone-dragging" : ""}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={handleDrop} data-testid="csv-dropzone">
              <input type="file" accept=".csv,text/csv" onChange={handleInput} data-testid="upload-csv-input" />
              <span className="drop-icon"><UploadCloud size={26} /></span>
              <strong>{file ? "Telemetry staged" : "Drop a CSV trace here"}</strong>
              <span>{fileSummary}</span>
              <span className="drop-action">{file ? "Choose another file" : "or browse local files"} <ArrowRight size={14} /></span>
            </label>
            <div className="preset-strip" data-testid="sample-presets">
              <div className="preset-heading"><span>REAL DATASETS</span><small>actual sampled .csv files</small></div>
              {datasets.isLoading && <p style={{ padding: "12px", opacity: 0.5, fontSize: "12px" }}>Loading datasets from disk...</p>}
              {datasets.data?.map((preset, index) => (
                 <button key={preset.id} className="preset-row" onClick={() => loadSample(preset.id, preset.name)} data-testid={`sample-preset-${index + 1}`}>
                   <span className="preset-number">0{index + 1}</span>
                   <span><strong>{preset.name}</strong><small>{(preset.size / 1024).toFixed(1)} KB real traffic trace</small></span>
                   <ChevronRight size={15} />
                 </button>
              ))}
            </div>
          </div>

          <div className="config-column">
            <div className="section-kicker" title="Configure the world model transition dynamics."><span>02</span> WORLD MODEL CONFIGURATION</div>
            <div className="config-panel" data-testid="rollout-configuration" style={{ background: "var(--card)", border: "2px solid var(--border)", borderRadius: "12px", boxShadow: "0 10px 30px rgba(0,0,0,0.05)" }}>
              <div className="config-panel-top"><div><h2 style={{ fontWeight: 800 }}>Define the world</h2><p style={{ opacity: 0.7 }}>Configure how the AI architecture learns state-transition dynamics P(S_t+1 | S_t).</p></div><span className="config-chip"><span className="status-dot" /> OFFLINE · Sequence Model</span></div>
              <div className="form-grid">
                <label className="field-label">MODEL ARCHITECTURE<select value={architecture} onChange={(event) => { setArchitecture(event.target.value); setExplainability(event.target.value.includes("Transformer") ? "Attention weights" : event.target.value.includes("LSTM") ? "Gradient sensitivity" : "SHAP Feature Attribution"); }} data-testid="architecture-select" style={{ background: "transparent", border: "1px solid var(--border)", padding: "12px" }}><option>RandomForest</option><option>LSTM State Encoder</option><option>Temporal Transformer</option></select></label>
                <label className="field-label">EXPLAINABILITY<select value={explainability} onChange={(event) => setExplainability(event.target.value)} disabled data-testid="explainability-select" style={{ background: "transparent", border: "1px solid var(--border)", padding: "12px" }}><option>Attention weights</option><option>SHAP Feature Attribution</option><option>Gradient sensitivity</option></select></label>
                <label className="field-label">FORWARD ROLLOUT<select value={horizon} onChange={(event) => setHorizon(event.target.value)} data-testid="horizon-select" style={{ background: "transparent", border: "1px solid var(--border)", padding: "12px" }}><option value="5">K = 5 steps</option><option value="8">K = 8 steps</option><option value="12">K = 12 steps</option><option value="20">K = 20 steps</option></select></label>
                <label className="field-label">STATE WINDOW<select value={windowSize} onChange={(event) => setWindowSize(event.target.value)} data-testid="window-size-select" style={{ background: "transparent", border: "1px solid var(--border)", padding: "12px" }}><option value="25">25 flows / state</option><option value="50">50 flows / state</option><option value="100">100 flows / state</option><option value="250">250 flows / state</option></select></label>
              </div>
              <div className="pipeline-row" data-testid="inference-pipeline"><span className="pipeline-step pipeline-step-active"><span>01</span> embed state S_t</span><span className="pipeline-arrow">→</span><span className="pipeline-step"><span>02</span> apply transition P(S_t+1|S_t)</span><span className="pipeline-arrow">→</span><span className="pipeline-step"><span>03</span> forward simulate</span><span className="pipeline-arrow">→</span><span className="pipeline-step"><span>04</span> explain attention</span></div>
              <Button className="run-button" disabled={!file || !inspection?.rows || runMutation.isPending} onClick={() => file && runMutation.mutate(file)} data-testid="run-inference-button" style={{ background: "#111", color: "#fff", borderRadius: "0", padding: "24px" }}><Play size={17} fill="currentColor" /> {runMutation.isPending ? "SIMULATING TRAJECTORY…" : "RUN FORWARD SIMULATION"}<ArrowRight size={17} /></Button>
              {runMutation.isError && <p className="inline-error" data-testid="inference-error">{formatError(runMutation.error)}</p>}
              <p className="config-footnote" style={{ opacity: 0.5 }}><Clock3 size={13} /> Generates timeline probability score and maps to MITRE ATT&amp;CK phases (Recon, Initial Access, and Exfiltration not available in training set)</p>
            </div>
          </div>
        </section>

        <section className="ingest-bottom-grid">
          <div className="inspector-panel" data-testid="dataset-inspector">
            <div className="section-kicker"><span>03</span> DATASET INSPECTOR</div>
            <div className="inspector-card"><div className="inspector-file"><FileSpreadsheet size={20} /><span><strong>{file ? file.name : "No dataset selected"}</strong><small>{file ? "CSV structure checked locally" : "Upload telemetry to preview its shape"}</small></span><Badge variant={file && inspection?.rows ? "default" : "outline"}>{file && inspection?.rows ? "READY" : "EMPTY"}</Badge></div><div className="inspector-stats"><span><strong data-testid="inspector-row-count">{inspection?.rows.toLocaleString() ?? "—"}</strong> rows detected</span><span><strong data-testid="inspector-field-count">{inspection?.headers.length ?? "—"}</strong> fields mapped</span><span><strong data-testid="inspector-window-count">{inspection ? detectedWindows : "—"}</strong> time windows</span></div>{inspection && <div className="inspector-features" data-testid="inspector-feature-groups"><div><span>FLOW FEATURES · {inspection.flowFeatures.length}</span><p>{(inspection.flowFeatures.length ? inspection.flowFeatures : inspection.headers).slice(0, 5).map((header) => <b key={header}>{header}</b>)}</p></div><div><span>PACKET / TIMING · {inspection.packetFeatures.length}</span><p>{(inspection.packetFeatures.length ? inspection.packetFeatures : ["Derived timing", "Port diversity"]).slice(0, 5).map((header) => <b key={header}>{header}</b>)}</p></div></div>}<div className="inspector-note"><FileUp size={15} /> {inspection ? "Counts update when you change the feature window." : "Flow and packet-level features will appear here before evaluation."}</div></div>
          </div>
          <div className="recent-panel" data-testid="recent-evaluations-panel">
            <div className="section-kicker"><span>04</span> RECENT EVALUATIONS <span className="section-count">{evaluations.data?.length ?? 0}</span><button className="icon-button" onClick={() => void evaluations.refetch()} data-testid="refresh-evaluations-button" aria-label="Refresh recent evaluations"><RefreshCw size={14} /></button></div>
            <div className="recent-list">{evaluations.data?.length ? evaluations.data.slice(0, 4).map((item) => <button className="recent-row" key={item.id} onClick={() => navigate(`/dashboard/${item.id}`)} data-testid={`recent-evaluation-${item.id}`}><span className="recent-risk" style={{ "--risk-width": `${Math.round(item.risk_score * 100)}%` } as CSSProperties}><span /></span><span className="recent-name"><strong>{item.filename}</strong><small>{item.rows} rows · {item.current_stage}</small></span><span className="recent-score">{Math.round(item.risk_score * 100)}%</span><ChevronRight size={14} /></button>) : <div className="empty-recent"><span>NO RECENT RUNS</span><small>Your first rollout will appear here.</small></div>}</div>
          </div>
        </section>
      </main>
    </div>
  );
}
