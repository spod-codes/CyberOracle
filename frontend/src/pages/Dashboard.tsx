import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowUpRight, Check, ChevronDown, CircleHelp, Download, Edit3, FileText, Filter, Gauge, MessageSquare, Pause, Play, RefreshCw, RotateCcw, Search, Send, ShieldAlert, Sparkles, Target, Trash2, X } from "lucide-react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, Radar, RadarChart, PolarGrid, PolarAngleAxis } from "recharts";

import AppHeader from "@/components/AppHeader";
import KernelTestConsole from "@/components/KernelTestConsole";
import { Button } from "@/components/ui/button";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";
import type { DeleteResponse, EvaluationRecord, FlowAlert, ReplayNote, ReplayNoteCreate, ReplayNoteUpdate } from "@/lib/types";

const metricNames: Record<string, string> = { f1: "F1 score", precision: "Precision", recall: "Recall", false_positive_rate: "False positive" };

function percent(value: number) { return `${Math.round(value * 100)}%`; }
function riskTone(value: number) { return value >= 0.82 ? "critical" : value >= 0.62 ? "high" : value >= 0.38 ? "medium" : "low"; }

export default function Dashboard() {
  const { evaluationId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [severity, setSeverity] = useState("All severities");
  const [stage, setStage] = useState("All stages");
  const [query, setQuery] = useState("");
  const [horizonView, setHorizonView] = useState(8);
  const [replayIndex, setReplayIndex] = useState(0);
  const [isReplaying, setIsReplaying] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [noteCategory, setNoteCategory] = useState("Finding");
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [editCategory, setEditCategory] = useState("Finding");
  const evaluation = useQuery({ queryKey: ["evaluation", evaluationId], queryFn: () => apiGet<EvaluationRecord>(`/evaluations/${evaluationId}`), enabled: Boolean(evaluationId), retry: false });
  const data = evaluation.data;

  const visibleFlows = useMemo(() => {
    if (!data) return [];
    return data.flows.filter((flow) => (severity === "All severities" || flow.severity === severity) && (stage === "All stages" || flow.stage === stage) && `${flow.source} ${flow.destination} ${flow.protocol} ${flow.signal}`.toLowerCase().includes(query.toLowerCase()));
  }, [data, query, severity, stage]);
  const chartData = useMemo(() => {
    if (!data) return [];
    const observed = data.timeline.filter((point) => point.kind === "observed");
    const forecast = data.timeline.filter((point) => point.kind === "forecast").slice(0, horizonView);
    return [...observed, ...forecast];
  }, [data, horizonView]);
  const observedTimeline = useMemo(() => data?.timeline.filter((point) => point.kind === "observed") ?? [], [data]);
  const selectedReplayIndex = Math.min(replayIndex, Math.max(0, observedTimeline.length - 1));
  const replayPoint = observedTimeline[selectedReplayIndex];
  const replayAttributions = useMemo(() => data?.attributions.slice(0, 3) ?? [], [data]);
  const selectedNotes = useMemo(() => data?.notes.filter((note) => note.window_label === replayPoint?.label) ?? [], [data, replayPoint?.label]);
  const noteMutation = useMutation({
    mutationFn: ({ text, window_label, category }: ReplayNoteCreate) => apiPost<ReplayNote>(`/evaluations/${evaluationId}/notes`, { text, window_label, category }),
    onSuccess: (createdNote) => {
      setNoteText("");
      queryClient.setQueryData<EvaluationRecord>(["evaluation", evaluationId], (current) => current ? { ...current, notes: [...current.notes, createdNote] } : current);
      toast.success("Replay note saved", { description: "It will also appear in the printable briefing." });
    },
  });
  const updateNoteMutation = useMutation({
    mutationFn: ({ noteId, update }: { noteId: string; update: ReplayNoteUpdate }) => apiPut<ReplayNote>(`/evaluations/${evaluationId}/notes/${noteId}`, update),
    onSuccess: (updatedNote) => {
      setEditingNoteId(null);
      queryClient.setQueryData<EvaluationRecord>(["evaluation", evaluationId], (current) => current ? { ...current, notes: current.notes.map((note) => note.id === updatedNote.id ? updatedNote : note) } : current);
      toast.success("Replay note updated");
    },
  });
  const deleteNoteMutation = useMutation({
    mutationFn: (noteId: string) => apiDelete<DeleteResponse>(`/evaluations/${evaluationId}/notes/${noteId}`),
    onSuccess: (_response, deletedNoteId) => {
      queryClient.setQueryData<EvaluationRecord>(["evaluation", evaluationId], (current) => current ? { ...current, notes: current.notes.filter((note) => note.id !== deletedNoteId) } : current);
      toast.success("Replay note removed");
    },
  });

  useEffect(() => {
    if (!isReplaying || observedTimeline.length < 2) return;
    const timer = window.setInterval(() => {
      setReplayIndex((current) => {
        if (current >= observedTimeline.length - 1) { setIsReplaying(false); return 0; }
        return current + 1;
      });
    }, 900);
    return () => window.clearInterval(timer);
  }, [isReplaying, observedTimeline.length]);

  useEffect(() => {
    if (data) setReplayIndex(Math.max(0, data.timeline.filter((point) => point.kind === "observed").length - 1));
  }, [data?.id]);

  useEffect(() => {
    if (data) setHorizonView(data.horizon);
  }, [data?.id]);

  useEffect(() => {
    if (data && location.hash === "#analyst-replay") window.requestAnimationFrame(() => document.querySelector('[data-testid="analyst-replay-panel"]')?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }, [data, location.hash]);

  const exportReport = () => {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${data.filename.replace(/\.csv$/i, "")}-aegis-report.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    toast.success("Report exported", { description: "The full evaluation JSON is ready for review." });
  };

  if (!data) {
    return <div className="app-shell" data-testid="dashboard-page"><AppHeader /><main className="dashboard-main"><div className="loading-panel" data-testid="dashboard-loading"><RefreshCw className="spin" size={18} /> {evaluation.isError ? "This evaluation is unavailable." : "Loading evaluation record…"}<Button variant="outline" onClick={() => navigate("/")} data-testid="back-to-ingest-button"><ArrowLeft size={15} /> back to ingest</Button></div></main></div>;
  }

  return (
    <div className="app-shell" data-testid="dashboard-page">
      <AppHeader />
      <main className="dashboard-main">
        {/* ── Page header ── */}
        <div className="dashboard-topline">
          <div>
            <div className="eyebrow"><span className="eyebrow-line" /> ACTIVE ANALYSIS / {data.id.slice(0, 8).toUpperCase()}</div>
            <h1>Trajectory command center</h1>
            <p className="dashboard-subtitle"><span className="file-pill"><Target size={13} /> {data.filename}</span> evaluated {new Date(data.created_at).toLocaleString()} · {data.model_status}</p>
          </div>
          <div className="top-actions">
            <Button variant="outline" onClick={() => navigate("/")} data-testid="new-evaluation-button"><ArrowLeft size={15} /> new evaluation</Button>
            <Button variant="outline" onClick={() => navigate(`/briefing/${data.id}`)} data-testid="open-briefing-button"><FileText size={15} /> briefing</Button>
            <Button onClick={exportReport} data-testid="export-report-button"><Download size={15} /> export report</Button>
          </div>
        </div>

        {/* ── Untrained model warning ── */}
        {data.model_status.includes("UNTRAINED") && (
          <div style={{ background: "#7f1d1d", color: "#fca5a5", padding: "12px 20px", borderRadius: "8px", marginBottom: "16px", display: "flex", alignItems: "center", gap: "10px", fontSize: "13px", fontFamily: "IBM Plex Mono" }}>
            <ShieldAlert size={16} style={{ flexShrink: 0 }} />
            <span>
              <strong>Untrained sequence model detected.</strong> Forecasts from this architecture use randomly initialized weights and are not meaningful.
              Run <code style={{ background: "rgba(255,255,255,0.15)", padding: "2px 6px", borderRadius: "4px" }}>python backend/train_sequence.py</code> to train and save real weights.
            </span>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════
            UNIFIED PREDICTION & INFERENCE BOX  (full-width at top)
        ══════════════════════════════════════════════════════════ */}
        <section className="pi-box" data-testid="prediction-inference-box">
          {/* Left: headline risk metrics */}
          <div className="pi-left">
            <div className="pi-kicker">
              <span className="status-pulse" />
              <span className="metric-overline">PREDICTION &amp; INFERENCE SUMMARY</span>
            </div>

            <div className="pi-metrics">
              <div className="pi-metric pi-metric--primary">
                <span className="metric-overline">OVERALL COMPROMISE RISK</span>
                <strong className="pi-risk-score">{percent(data.risk_score)}</strong>
                <small>trajectory is {data.risk_score >= 0.62 ? "accelerating" : "being monitored"}</small>
              </div>
              <div className="pi-metric">
                <span className="metric-overline">CURRENT PHASE</span>
                <strong>{data.current_stage}</strong>
                <small>present state estimate</small>
              </div>
              <div className="pi-metric">
                <span className="metric-overline">K-STEP FORWARD</span>
                <strong>{percent(data.forecast_probability)}</strong>
                <small>→ {data.forecast_stage}</small>
              </div>
              <div className="pi-metric">
                <span className="metric-overline">EARLY-WARNING LEAD</span>
                <strong>{data.lead_windows} <small style={{ fontSize: "13px" }}>windows</small></strong>
                <small>before expected transition</small>
              </div>
            </div>
          </div>

          {/* Divider */}
          <div className="pi-divider" />

          {/* Right: graphic warning */}
          <div className="pi-right" style={{ display: "flex", flexDirection: "column", justifyContent: "center", padding: "24px" }}>
             <div style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "16px" }}>
                <div style={{ background: "rgba(255, 77, 48, 0.1)", borderRadius: "50%", padding: "16px" }}>
                   <ShieldAlert size={42} color="#ff4d30" />
                </div>
                <div>
                   <h3 style={{ fontSize: "24px", color: "#edf4ef", margin: 0 }}>Attack in progress</h3>
                   <p style={{ color: "#adbbb2", margin: 0, marginTop: "4px" }}>The AI has confidently identified a coordinated attack.</p>
                </div>
             </div>
             <p style={{ fontSize: "15px", lineHeight: "1.6", color: "#edf4ef", margin: 0, borderLeft: "4px solid #00e5ff", paddingLeft: "16px" }}>
                The attacker has breached the network and is currently performing <strong>{data.current_stage}</strong>. 
                Based on current momentum, they are projected to escalate to <strong>{data.forecast_stage}</strong> within the next {data.lead_windows} time steps.
             </p>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            SECTION 01 — TEMPORAL INFILTRATION TIMELINE
        ══════════════════════════════════════════════════ */}
        <section className="db-section chart-panel" data-testid="infiltration-timeline">
          <div className="panel-heading">
            <div>
              <div className="section-kicker" title="Shows how the risk changes over time.">
                <span>01</span> TEMPORAL INFILTRATION TIMELINE
              </div>
              <h2>Probability of converging toward compromise</h2>
            </div>
            <div className="chart-controls">
              <span className="chart-legend">
                <i className="legend-observed" /> observed <i className="legend-forecast" /> predicted
              </span>
              <select value={horizonView} onChange={(e) => setHorizonView(Number(e.target.value))} data-testid="timeline-horizon-select">
                <option value="5">K = 5</option>
                <option value="8">K = 8</option>
                <option value="12">K = 12</option>
              </select>
            </div>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={chartData} margin={{ top: 18, right: 8, left: -16, bottom: 0 }}>
                <defs>
                  <linearGradient id="riskGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ff2a55" stopOpacity={0.38} />
                    <stop offset="100%" stopColor="#ff2a55" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#dce8df" strokeDasharray="2 5" vertical={false} />
                <XAxis dataKey="label" stroke="#9aaba3" tick={{ fill: "#75857d", fontSize: 11, fontFamily: "IBM Plex Mono" }} tickLine={false} axisLine={false} />
                <YAxis domain={[0, 1]} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} stroke="#9aaba3" tick={{ fill: "#75857d", fontSize: 11, fontFamily: "IBM Plex Mono" }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #dce8df", borderRadius: 8, color: "#1f302c", fontFamily: "IBM Plex Mono", fontSize: 11 }} formatter={(v) => [percent(Number(v ?? 0)), "infiltration probability"] as [string, string]} />
                <ReferenceLine y={0.62} stroke="#d49a37" strokeDasharray="4 4" label={{ value: "early warning threshold", fill: "#b47719", fontSize: 10, position: "insideTopRight" }} />
                <Area type="monotone" dataKey="probability" stroke="#e77969" strokeWidth={2.5} fill="url(#riskGradient)" activeDot={{ r: 5, fill: "#9ed7ba", stroke: "#ffffff", strokeWidth: 2 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="chart-foot">
            <span><span className="chart-dot chart-dot-red" /> observed state windows</span>
            <span><span className="chart-dot chart-dot-cyan" /> rollout begins at {data.timeline.find((p) => p.kind === "forecast")?.label}</span>
            <span className="chart-foot-end">threshold = 62%</span>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            SECTION 02 — ANALYST REPLAY
        ══════════════════════════════════════════════════ */}
        <section className="replay-panel db-section" data-testid="analyst-replay-panel">
          <div className="panel-heading">
            <div>
              <div className="section-kicker"><span>02</span> ANALYST REPLAY</div>
              <h2>Walk the state before the forecast</h2>
              <p>Scrub observed windows or play the trajectory to inspect how evidence shifts.</p>
            </div>
            <div className="replay-actions">
              <button className="replay-control replay-control-primary" onClick={() => setIsReplaying((p) => !p)} data-testid="replay-play-pause-button">
                {isReplaying ? <Pause size={14} /> : <Play size={14} fill="currentColor" />} {isReplaying ? "pause" : "play replay"}
              </button>
              <button className="replay-control" onClick={() => { setIsReplaying(false); setReplayIndex(0); }} data-testid="replay-reset-button">
                <RotateCcw size={13} /> reset
              </button>
            </div>
          </div>
          <div className="replay-body">
            <div className="replay-scrubber">
              <div className="replay-scrubber-head"><span>OBSERVED WINDOW {selectedReplayIndex + 1} / {observedTimeline.length}</span><strong>{replayPoint?.label ?? "—"}</strong></div>
              <input type="range" min="0" max={Math.max(0, observedTimeline.length - 1)} value={selectedReplayIndex} onChange={(e) => { setIsReplaying(false); setReplayIndex(Number(e.target.value)); }} data-testid="replay-scrubber" />
              <div className="replay-ticks">{observedTimeline.map((point, index) => <button key={point.label} className={index === selectedReplayIndex ? "replay-tick replay-tick-active" : "replay-tick"} onClick={() => { setIsReplaying(false); setReplayIndex(index); }} data-testid={`replay-window-${index + 1}`}>{point.label}</button>)}</div>
            </div>
            <div className="replay-state-card">
              <span className="metric-overline" title="A compact summary of network behaviour at this moment.">SELECTED LATENT STATE</span>
              <div className="replay-state-main"><strong>{percent(replayPoint?.probability ?? 0)}</strong><span className={`signal-badge tone-${riskTone(replayPoint?.probability ?? 0)}`}><span className="status-dot" /> {replayPoint?.stage ?? "Awaiting state"}</span></div>
              <small>state likelihood at this observed window</small>
            </div>
            <div className="replay-evidence">
              <span className="metric-overline">TOP SHIFTING EVIDENCE</span>
              {replayAttributions.map((item) => <div className="replay-evidence-row" key={item.feature}><span>{item.feature}</span><strong>+{Math.round(item.weight * 100)}%</strong></div>)}
            </div>
          </div>
          <div className="replay-notes" data-testid="replay-notes-panel">
            <datalist id="note-category-options"><option value="Finding" /><option value="Action" /><option value="Escalation" /></datalist>
            <div className="replay-note-heading"><span><MessageSquare size={15} /> NOTES FOR {replayPoint?.label ?? "WINDOW"}</span><small>{selectedNotes.length} saved</small></div>
            <div className="replay-note-list">{selectedNotes.length ? selectedNotes.map((note) => <div className="replay-note" key={note.id} data-testid={`replay-note-${note.id}`}>{editingNoteId === note.id ? <div className="replay-note-edit"><input list="note-category-options" value={editCategory} onChange={(e) => setEditCategory(e.target.value)} maxLength={40} /><textarea value={editText} onChange={(e) => setEditText(e.target.value)} maxLength={400} rows={2} /><div><button onClick={() => updateNoteMutation.mutate({ noteId: note.id, update: { text: editText.trim(), category: editCategory.trim() } })} disabled={!editText.trim() || !editCategory.trim() || updateNoteMutation.isPending}><Check size={13} /> save</button><button onClick={() => setEditingNoteId(null)}><X size={13} /> cancel</button></div></div> : <><div className="replay-note-meta"><span className={`note-category note-category-${note.category.toLowerCase()}`}>{note.category}</span><div><button onClick={() => { setEditingNoteId(note.id); setEditText(note.text); setEditCategory(note.category); }} aria-label="Edit replay note"><Edit3 size={13} /></button><button onClick={() => { if (window.confirm("Delete this replay note?")) deleteNoteMutation.mutate(note.id); }} aria-label="Delete replay note"><Trash2 size={13} /></button></div></div><p>{note.text}</p><small>{note.updated_at ? `Updated ${new Date(note.updated_at).toLocaleString()}` : new Date(note.created_at).toLocaleString()}</small></>}</div>) : <div className="replay-note-empty">No notes for this window yet. Add a short defender observation below.</div>}</div>
            <form className="replay-note-form" onSubmit={(e) => { e.preventDefault(); if (replayPoint && noteText.trim() && noteCategory.trim()) noteMutation.mutate({ text: noteText.trim(), window_label: replayPoint.label, category: noteCategory.trim() }); }}>
              <input className="note-category-input" list="note-category-options" value={noteCategory} onChange={(e) => setNoteCategory(e.target.value)} maxLength={40} aria-label="Note category" />
              <textarea value={noteText} onChange={(e) => setNoteText(e.target.value)} maxLength={400} rows={2} placeholder={`Add a plain-language note for ${replayPoint?.label ?? "this window"}…`} data-testid="replay-note-input" />
              <button type="submit" disabled={!noteText.trim() || !noteCategory.trim() || !replayPoint || noteMutation.isPending} data-testid="save-replay-note-button"><Send size={14} /> {noteMutation.isPending ? "saving…" : "save note"}</button>
            </form>
            {(noteMutation.isError || updateNoteMutation.isError || deleteNoteMutation.isError) && <p className="replay-note-error" data-testid="replay-note-error">The note change could not be saved. Please try again.</p>}
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            SECTION 03 — MITRE ATT&CK STAGES
        ══════════════════════════════════════════════════ */}
        <section className="stage-panel db-section" data-testid="mitre-stage-panel">
          <div className="panel-heading">
            <div>
              <div className="section-kicker" title="The standard stages used to describe how an attack moves through a network."><span>03</span> ATTACKER PROGRESSION</div>
              <h2>MITRE ATT&amp;CK trajectory mapping</h2>
            </div>
            <span className="mapping-note"><CircleHelp size={14} /> predicted state mapping</span>
          </div>
          <div className="stage-track">{data.stages.map((item, index) => <div className={`stage-node stage-${item.status}`} key={item.name} data-testid={`mitre-stage-${item.short_name.toLowerCase()}`}><div className="stage-connector">{index > 0 && <span />}</div><div className="stage-icon">{item.status === "current" ? <Target size={15} /> : item.status === "complete" ? <span>✓</span> : <span>{String(index + 1).padStart(2, "0")}</span>}</div><div className="stage-text"><strong>{item.name}</strong><small>{item.tactic}</small><span>{percent(item.probability)} likelihood</span></div></div>)}</div>
        </section>

        {/* ══════════════════════════════════════════════════
            SECTION 04 — EXPLAINABILITY
        ══════════════════════════════════════════════════ */}
        <section className="evidence-grid">
          <div className="attribution-panel" data-testid="explainability-panel" style={{ width: "100%" }}>
            <div className="panel-heading">
              <div>
                <div className="section-kicker" title="Network signals that most influenced the prediction."><span>04</span> EXPLAINABILITY / {data.explainability.toUpperCase()}</div>
                <h2>What is driving the trajectory?</h2>
              </div>
              <span className="verified-label"><span className="status-dot" /> evidence attached</span>
            </div>
            <div style={{ height: "240px", marginTop: "1rem", marginBottom: "1rem", overflowY: "auto" }}>
              {data.forecast_method === "attention_weights" ? (
                <div>
                  <h4 style={{ color: "#9aaba3", marginBottom: "10px", fontSize: "12px", letterSpacing: "1px" }}>SELF-ATTENTION WEIGHTS (per time window)</h4>
                  <div style={{ display: "flex", gap: "2px", height: "40px", marginBottom: "16px" }}>
                    {data.attention_weights?.map((w, i) => (
                      <div key={i} title={`T-${15 - i}: ${w.toFixed(3)}`} style={{ flex: 1, backgroundColor: `rgba(231,121,105, ${Math.max(0.1, w / (Math.max(...(data.attention_weights || [])) || 1))})`, borderRadius: "2px" }} />
                    ))}
                  </div>
                  {data.attributions.map(a => (
                     <div key={a.feature} style={{ display: "flex", justifyContent: "space-between", fontSize: "13px", borderBottom: "1px solid #dce8df", padding: "8px 0", color: "#1f302c" }}>
                        <strong>{a.feature}</strong>
                        <span>{a.value}</span>
                     </div>
                  ))}
                </div>
              ) : data.forecast_method === "gradient" ? (
                <div>
                  <h4 style={{ color: "#9aaba3", marginBottom: "10px", fontSize: "12px", letterSpacing: "1px" }}>GRADIENT SENSITIVITY</h4>
                  {data.attributions.map(a => (
                     <div key={a.feature} style={{ display: "flex", justifyContent: "space-between", fontSize: "13px", borderBottom: "1px solid #dce8df", padding: "8px 0", color: "#1f302c" }}>
                        <strong>{a.feature}</strong>
                        <span>{a.value}</span>
                     </div>
                  ))}
                </div>
              ) : (
                <div>
                  <h4 style={{ color: "#9aaba3", marginBottom: "10px", fontSize: "12px", letterSpacing: "1px" }}>SHAP FEATURE ATTRIBUTION</h4>
                  {data.attributions.map(a => (
                     <div key={a.feature} style={{ marginBottom: "12px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px", marginBottom: "4px", color: "#1f302c" }}>
                           <strong>{a.feature}</strong>
                           <span style={{ color: a.direction === "increases risk" ? "#e77969" : "#5e9870" }}>{a.weight * 100}%</span>
                        </div>
                        <div style={{ width: "100%", height: "4px", backgroundColor: "#e1ebe3", borderRadius: "2px", overflow: "hidden" }}>
                           <div style={{ width: `${a.weight * 100}%`, height: "100%", backgroundColor: a.direction === "increases risk" ? "#e77969" : "#5e9870" }} />
                        </div>
                     </div>
                  ))}
                </div>
              )}
            </div>
            <div style={{ marginTop: "1rem", paddingTop: "1rem", borderTop: "1px solid #2b3b31" }}>
               <KernelTestConsole evaluationId={data.id} />
            </div>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════
            SECTION 06 — TELEMETRY EXPLORER
        ══════════════════════════════════════════════════ */}
        <section className="flow-panel db-section" data-testid="flow-explorer">
          <div className="panel-heading">
            <div>
              <div className="section-kicker"><span>06</span> TELEMETRY EXPLORER</div>
              <h2>Flagged network flows <span className="flow-count">{visibleFlows.length} / {data.flows.length}</span></h2>
            </div>
            <div className="flow-summary"><span className="summary-dot" /> {data.rows.toLocaleString()} rows analyzed <span className="summary-separator" /> {data.features} fields mapped</div>
          </div>
          <div className="filter-bar">
            <label className="search-field"><Search size={15} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search host, protocol, signal…" data-testid="flow-search-input" />{query && <button onClick={() => setQuery("")} aria-label="Clear flow search"><X size={13} /></button>}</label>
            <label className="filter-select"><Filter size={14} /><select value={severity} onChange={(e) => setSeverity(e.target.value)} data-testid="severity-filter"><option>All severities</option><option>Critical</option><option>High</option><option>Medium</option><option>Low</option></select><ChevronDown size={13} /></label>
            <label className="filter-select"><select value={stage} onChange={(e) => setStage(e.target.value)} data-testid="stage-filter"><option>All stages</option><option>Reconnaissance</option><option>Initial Access</option><option>Lateral Movement</option><option>Command &amp; Control</option><option>Exfiltration</option></select><ChevronDown size={13} /></label>
            <button className="reset-filter" onClick={() => { setQuery(""); setSeverity("All severities"); setStage("All stages"); }} data-testid="reset-flow-filters">reset filters</button>
          </div>
          <div className="flow-table-wrap">
            <table className="flow-table">
              <thead><tr><th>FLOW ID / TIME</th><th>SOURCE → DESTINATION</th><th>PROTOCOL</th><th>FLAGS</th><th>ATT&amp;CK STAGE</th><th>RISK</th></tr></thead>
              <tbody>{visibleFlows.slice(0, 12).map((flow: FlowAlert) => <tr key={flow.id} data-testid={`flagged-flow-row-${flow.id}`}><td><strong>{flow.id}</strong><small>{flow.timestamp}</small></td><td><strong>{flow.source}</strong><small>→ {flow.destination}</small></td><td><span className="protocol-tag">{flow.protocol}</span></td><td className="mono-cell">{flow.flags}</td><td><span className={`stage-tag tone-${riskTone(flow.risk)}`}>{flow.stage}</span><small>{flow.signal}</small></td><td><strong className={`risk-text tone-text-${riskTone(flow.risk)}`}>{percent(flow.risk)}</strong><span className="mini-risk"><span style={{ width: `${flow.risk * 100}%` }} /></span></td></tr>)}</tbody>
            </table>
            {visibleFlows.length === 0 && <div className="empty-flows" data-testid="empty-flow-state"><Search size={18} /> No flows match these filters.</div>}
          </div>
          <div className="flow-footer"><span>Showing top 12 risk-ranked records</span><span className="data-source"><span className="status-dot" /> local CSV source</span></div>
        </section>
      </main>
    </div>
  );
}
