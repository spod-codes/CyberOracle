import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, Printer, Save, ShieldCheck } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import AppHeader from "@/components/AppHeader";
import { Button } from "@/components/ui/button";
import { apiGet, apiPut } from "@/lib/api";
import type { BriefingSignoff, BriefingSignoffUpdate, EvaluationRecord } from "@/lib/types";

function percent(value: number) { return `${Math.round(value * 100)}%`; }

export default function Briefing() {
  const { evaluationId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [analystName, setAnalystName] = useState("");
  const [reviewStatus, setReviewStatus] = useState("Draft");
  const [approvalDate, setApprovalDate] = useState("");
  const evaluation = useQuery({ queryKey: ["evaluation", evaluationId], queryFn: () => apiGet<EvaluationRecord>(`/evaluations/${evaluationId}`), enabled: Boolean(evaluationId), retry: false });
  const data = evaluation.data;

  useEffect(() => {
    if (!data) return;
    setAnalystName(data.signoff.analyst_name);
    setReviewStatus(data.signoff.status);
    setApprovalDate(data.signoff.approval_date ?? "");
  }, [data?.id, data?.signoff.updated_at]);

  const signoffMutation = useMutation({
    mutationFn: (update: BriefingSignoffUpdate) => apiPut<BriefingSignoff>(`/evaluations/${evaluationId}/signoff`, update),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["evaluation", evaluationId] });
      toast.success("Briefing signoff saved", { description: "The printable report is up to date." });
    },
  });

  if (!data) {
    return <div className="app-shell" data-testid="briefing-page"><AppHeader /><main className="briefing-main"><div className="loading-panel">{evaluation.isError ? "This briefing is unavailable." : "Preparing print-ready briefing…"}<Button variant="outline" onClick={() => navigate("/")} data-testid="briefing-back-button"><ArrowLeft size={15} /> back to ingest</Button></div></main></div>;
  }

  const submitSignoff = () => {
    const effectiveDate = reviewStatus === "Approved" && !approvalDate ? new Date().toISOString().slice(0, 10) : approvalDate || null;
    if (!analystName.trim()) return;
    signoffMutation.mutate({ analyst_name: analystName.trim(), status: reviewStatus, approval_date: effectiveDate });
  };

  return (
    <div className="app-shell" data-testid="briefing-page">
      <div className="print-hide"><AppHeader /></div>
      <main className="briefing-main">
        <div className="briefing-actions print-hide">
          <Button variant="outline" onClick={() => navigate(`/dashboard/${data.id}`)} data-testid="briefing-back-dashboard-button"><ArrowLeft size={15} /> back to dashboard</Button>
          <Button onClick={() => window.print()} data-testid="print-briefing-button"><Printer size={15} /> save as PDF</Button>
        </div>
        <article className="briefing-document">
          <header className="briefing-document-header">
            <div className="briefing-brand"><span className="briefing-mark"><ShieldCheck size={21} /></span><span><strong>CYBER ORACLE</strong><small>predictive cyber defence · analyst briefing</small></span></div>
            <div className="briefing-meta"><span>ANALYSIS ID</span><strong>{data.id.slice(0, 12).toUpperCase()}</strong><span>{new Date(data.created_at).toLocaleString()}</span></div>
          </header>
          <section className="briefing-title"><div className="eyebrow"><span className="eyebrow-line" /> EXECUTIVE + ANALYST BRIEFING</div><h1>Predictive network trajectory</h1><p><strong>{data.filename}</strong> · {data.rows.toLocaleString()} telemetry rows · {data.architecture} · {data.model_status}</p></section>
          <section className="briefing-summary-grid">
            <div className="briefing-summary-risk"><span>OVERALL COMPROMISE RISK</span><strong>{percent(data.risk_score)}</strong><small>forward outlook: {data.forecast_stage}</small></div>
            <div><span>OBSERVED PHASE</span><strong>{data.current_stage}</strong><small>current network state</small></div>
            <div><span>EARLY WARNING</span><strong>{data.lead_windows} windows</strong><small>before expected transition</small></div>
            <div><span>FORECAST HORIZON</span><strong>K = {data.horizon}</strong><small>{percent(data.forecast_probability)} final probability</small></div>
          </section>
          <section className="briefing-section"><div className="briefing-section-title"><span>01</span><h2>Executive assessment</h2></div><div className="briefing-callout"><strong>Analyst readout</strong><p>The temporal state trajectory is converging toward <b>{data.forecast_stage}</b>. Cyber Oracle detected rising transition momentum across the observed telemetry and projects an early-warning lead of <b>{data.lead_windows} windows</b> before the expected stage transition.</p></div><div className="briefing-timeline"><div className="briefing-axis">{data.timeline.map((point) => <div className={point.kind === "forecast" ? "briefing-point briefing-point-forecast" : "briefing-point"} key={point.label}><span style={{ height: `${Math.max(8, point.probability * 100)}%` }} /><small>{point.label}</small><strong>{percent(point.probability)}</strong></div>)}</div></div></section>
          <section className="briefing-section"><div className="briefing-section-title"><span>02</span><h2>MITRE ATT&CK progression</h2></div><div className="briefing-stages">{data.stages.map((stage) => <div className={`briefing-stage briefing-stage-${stage.status}`} key={stage.name}><span>{stage.status === "current" ? "CURRENT" : stage.status.toUpperCase()}</span><strong>{stage.name}</strong><small>{stage.tactic} · {percent(stage.probability)} likelihood</small></div>)}</div></section>
          <section className="briefing-two-col">
            <div className="briefing-section"><div className="briefing-section-title"><span>03</span><h2>Driving evidence</h2></div><div className="briefing-evidence">{data.attributions.map((item, index) => <div key={item.feature}><span>0{index + 1}</span><strong>{item.feature}</strong><em>+{Math.round(item.weight * 100)}%</em><small>{item.value} · {item.explanation}</small></div>)}</div></div>
            <div className="briefing-section"><div className="briefing-section-title"><span>04</span><h2>Benchmark ledger</h2></div><table className="briefing-table"><thead><tr><th>Metric</th><th>World model</th><th>Baseline</th><th>Lift</th></tr></thead><tbody>{Object.entries(data.benchmark.world_model).map(([key, value]) => <tr key={key}><td>{key.replaceAll("_", " ")}</td><td>{percent(value)}</td><td>{percent(data.benchmark.logistic_baseline[key])}</td><td>+{percent(data.benchmark.lift[key])}</td></tr>)}</tbody></table></div>
          </section>
          {data.notes.length > 0 && <section className="briefing-section" data-testid="briefing-notes-section"><div className="briefing-section-title"><span>05</span><h2>Analyst replay notes</h2><small>{data.notes.length} saved observation{data.notes.length === 1 ? "" : "s"}</small></div><div className="briefing-notes">{data.notes.map((note) => <div className="briefing-note" key={note.id}><div><span>{note.window_label}</span><b className={`note-category note-category-${note.category.toLowerCase()}`}>{note.category}</b></div><p>{note.text}</p><small>{note.updated_at ? `Updated ${new Date(note.updated_at).toLocaleString()}` : new Date(note.created_at).toLocaleString()}</small></div>)}</div></section>}
          <section className="briefing-section briefing-signoff-section" data-testid="briefing-signoff-section">
            <div className="briefing-section-title"><span>{data.notes.length > 0 ? "06" : "05"}</span><h2>Briefing signoff</h2><small>review ownership and approval</small></div>
            <div className="briefing-signoff-summary"><div><span>ANALYST</span><strong>{data.signoff.analyst_name || "Not assigned"}</strong></div><div><span>REVIEW STATUS</span><strong className={`signoff-status signoff-${data.signoff.status.toLowerCase().replaceAll(" ", "-")}`}>{data.signoff.status}</strong></div><div><span>APPROVAL DATE</span><strong>{data.signoff.approval_date || "Pending"}</strong></div><div><span>LAST UPDATED</span><strong>{data.signoff.updated_at ? new Date(data.signoff.updated_at).toLocaleString() : "Not signed"}</strong></div></div>
            <form className="briefing-signoff-form print-hide" onSubmit={(event) => { event.preventDefault(); submitSignoff(); }}><label>ANALYST NAME<input value={analystName} onChange={(event) => setAnalystName(event.target.value)} maxLength={100} placeholder="e.g. A. Sharma" data-testid="signoff-analyst-input" /></label><label>REVIEW STATUS<select value={reviewStatus} onChange={(event) => { setReviewStatus(event.target.value); if (event.target.value === "Approved" && !approvalDate) setApprovalDate(new Date().toISOString().slice(0, 10)); }} data-testid="signoff-status-select"><option>Draft</option><option>In Review</option><option>Approved</option><option>Escalated</option></select></label><label>APPROVAL DATE<input type="date" value={approvalDate} onChange={(event) => setApprovalDate(event.target.value)} data-testid="signoff-date-input" /></label><button type="submit" disabled={!analystName.trim() || signoffMutation.isPending} data-testid="save-signoff-button"><Save size={14} /> {signoffMutation.isPending ? "saving…" : "save signoff"}</button></form>
            {signoffMutation.isSuccess && <p className="signoff-saved print-hide" data-testid="signoff-saved-message"><CheckCircle2 size={14} /> Saved to this evaluation and ready to print.</p>}
          </section>
          <section className="briefing-section briefing-flow-section"><div className="briefing-section-title"><span>{data.notes.length > 0 ? "07" : "06"}</span><h2>Flagged telemetry · analyst detail</h2><small>{data.flows.length} records · {data.features} mapped fields</small></div><table className="briefing-table briefing-flow-table"><thead><tr><th>Flow</th><th>Source → destination</th><th>Stage</th><th>Signal</th><th>Risk</th></tr></thead><tbody>{data.flows.slice(0, 15).map((flow) => <tr key={flow.id}><td>{flow.id}<small>{flow.timestamp}</small></td><td>{flow.source}<small>→ {flow.destination}</small></td><td>{flow.stage}</td><td>{flow.signal}</td><td>{percent(flow.risk)}</td></tr>)}</tbody></table></section>
          <footer className="briefing-footer"><span>CYBER ORACLE · offline deterministic evaluation runtime</span><span>Generated for defender review</span></footer>
        </article>
      </main>
    </div>
  );
}