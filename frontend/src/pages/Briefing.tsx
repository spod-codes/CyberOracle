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
          <section className="briefing-summary-grid" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "12px", marginBottom: "24px" }}>
            <div className="briefing-summary-risk" style={{ border: "2px solid #ff4d30", background: "rgba(255, 77, 48, 0.05)" }}><span>OVERALL THREAT LEVEL</span><strong style={{ fontSize: "36px", color: "#ff4d30" }}>{percent(data.risk_score)}</strong><small>Likelihood of a successful attack</small></div>
            <div><span>CURRENT ATTACK PHASE</span><strong style={{ fontSize: "24px" }}>{data.current_stage}</strong><small>What the attacker is doing now</small></div>
            <div><span>ESTIMATED TIME TO ACT</span><strong style={{ fontSize: "24px", color: "#00e5ff" }}>{data.lead_windows} windows</strong><small>Before the attack worsens</small></div>
            <div><span>NEXT LIKELY TARGET</span><strong style={{ fontSize: "24px" }}>{data.forecast_stage}</strong><small>What they will likely do next</small></div>
          </section>
          <section className="briefing-section">
             <div className="briefing-section-title"><span>01</span><h2>Executive Assessment (Plain English)</h2></div>
             <div className="briefing-callout" style={{ fontSize: "14px", lineHeight: "1.6", borderLeft: "4px solid #00e5ff", paddingLeft: "16px" }}>
                <p style={{ marginBottom: "12px" }}><strong>What is happening?</strong><br/>Cyber Oracle has analyzed {data.rows.toLocaleString()} events from your network traffic. The AI has detected a pattern that strongly resembles a coordinated cyber attack. Right now, the attacker is primarily focused on <b>{data.current_stage}</b>, meaning they have already gained a foothold and are progressing through your network.</p>
                <p style={{ marginBottom: "12px" }}><strong>What is the risk?</strong><br/>The overall threat level is currently at <b>{percent(data.risk_score)}</b>. This is a critical warning. The network traffic patterns indicate that the attacker is actively moving toward the <b>{data.forecast_stage}</b> phase.</p>
                <p><strong>What should we do?</strong><br/>You have an estimated early-warning window of <b>{data.lead_windows} time steps</b> before the attacker reaches their next objective. Security teams should immediately investigate the flagged telemetry below and isolate affected systems before the attack escalates.</p>
             </div>
             <div className="briefing-timeline" style={{ marginTop: "24px" }}><div className="briefing-axis">{data.timeline.map((point) => <div className={point.kind === "forecast" ? "briefing-point briefing-point-forecast" : "briefing-point"} key={point.label}><span style={{ height: `${Math.max(8, point.probability * 100)}%`, background: point.kind === "forecast" ? "#ff4d30" : "#00e5ff", opacity: point.kind === "forecast" ? 0.8 : 0.4 }} /><small style={{ fontSize: "9px" }}>{point.label}</small><strong style={{ fontSize: "11px" }}>{percent(point.probability)}</strong></div>)}</div></div>
          </section>
          <section className="briefing-section"><div className="briefing-section-title"><span>02</span><h2>Attack Progression Map</h2></div><div className="briefing-stages">{data.stages.map((stage) => <div className={`briefing-stage briefing-stage-${stage.status}`} key={stage.name} style={{ opacity: stage.status === "pending" ? 0.4 : 1, border: stage.status === "current" ? "1px solid #00e5ff" : undefined }}><span>{stage.status === "current" ? "HAPPENING NOW" : stage.status === "complete" ? "ALREADY OCCURRED" : "EXPECTED LATER"}</span><strong style={{ color: stage.status === "current" ? "#00e5ff" : undefined }}>{stage.name}</strong><small>{stage.tactic}</small></div>)}</div></section>
          <section className="briefing-two-col">
            <div className="briefing-section" style={{ width: "100%" }}><div className="briefing-section-title"><span>03</span><h2>What triggered this warning?</h2><small>The specific network behaviors the AI flagged</small></div><div className="briefing-evidence">{data.attributions.map((item, index) => <div key={item.feature} style={{ padding: "12px", borderBottom: "1px solid #2b3b31" }}><span>0{index + 1}</span><strong style={{ fontSize: "14px", display: "block", marginBottom: "4px" }}>{item.feature}</strong><em style={{ color: "#ff4d30", display: "block", marginBottom: "4px" }}>Impact: {Math.round(item.weight * 100)}%</em><small style={{ color: "#9aaba3" }}>{item.value} · {item.explanation}</small></div>)}</div></div>
          </section>
          {data.notes.length > 0 && <section className="briefing-section" data-testid="briefing-notes-section"><div className="briefing-section-title"><span>04</span><h2>Analyst replay notes</h2><small>{data.notes.length} saved observation{data.notes.length === 1 ? "" : "s"}</small></div><div className="briefing-notes">{data.notes.map((note) => <div className="briefing-note" key={note.id}><div><span>{note.window_label}</span><b className={`note-category note-category-${note.category.toLowerCase()}`}>{note.category}</b></div><p>{note.text}</p><small>{note.updated_at ? `Updated ${new Date(note.updated_at).toLocaleString()}` : new Date(note.created_at).toLocaleString()}</small></div>)}</div></section>}
          <section className="briefing-section briefing-signoff-section" data-testid="briefing-signoff-section">
            <div className="briefing-section-title"><span>{data.notes.length > 0 ? "05" : "04"}</span><h2>Briefing signoff</h2><small>review ownership and approval</small></div>
            <div className="briefing-signoff-summary"><div><span>ANALYST</span><strong>{data.signoff.analyst_name || "Not assigned"}</strong></div><div><span>REVIEW STATUS</span><strong className={`signoff-status signoff-${data.signoff.status.toLowerCase().replaceAll(" ", "-")}`}>{data.signoff.status}</strong></div><div><span>APPROVAL DATE</span><strong>{data.signoff.approval_date || "Pending"}</strong></div><div><span>LAST UPDATED</span><strong>{data.signoff.updated_at ? new Date(data.signoff.updated_at).toLocaleString() : "Not signed"}</strong></div></div>
            <form className="briefing-signoff-form print-hide" onSubmit={(event) => { event.preventDefault(); submitSignoff(); }}><label>ANALYST NAME<input value={analystName} onChange={(event) => setAnalystName(event.target.value)} maxLength={100} placeholder="e.g. A. Sharma" data-testid="signoff-analyst-input" /></label><label>REVIEW STATUS<select value={reviewStatus} onChange={(event) => { setReviewStatus(event.target.value); if (event.target.value === "Approved" && !approvalDate) setApprovalDate(new Date().toISOString().slice(0, 10)); }} data-testid="signoff-status-select"><option>Draft</option><option>In Review</option><option>Approved</option><option>Escalated</option></select></label><label>APPROVAL DATE<input type="date" value={approvalDate} onChange={(event) => setApprovalDate(event.target.value)} data-testid="signoff-date-input" /></label><button type="submit" disabled={!analystName.trim() || signoffMutation.isPending} data-testid="save-signoff-button"><Save size={14} /> {signoffMutation.isPending ? "saving…" : "save signoff"}</button></form>
            {signoffMutation.isSuccess && <p className="signoff-saved print-hide" data-testid="signoff-saved-message"><CheckCircle2 size={14} /> Saved to this evaluation and ready to print.</p>}
          </section>
          <section className="briefing-section briefing-flow-section"><div className="briefing-section-title"><span>{data.notes.length > 0 ? "06" : "05"}</span><h2>Flagged telemetry</h2><small>{data.flows.length} records · {data.features} mapped fields</small></div><table className="briefing-table briefing-flow-table"><thead><tr><th>Flow</th><th>Source → destination</th><th>Stage</th><th>Signal</th><th>Risk</th></tr></thead><tbody>{data.flows.slice(0, 15).map((flow) => <tr key={flow.id}><td>{flow.id}<small>{flow.timestamp}</small></td><td>{flow.source}<small>→ {flow.destination}</small></td><td>{flow.stage}</td><td>{flow.signal}</td><td>{percent(flow.risk)}</td></tr>)}</tbody></table></section>
          <footer className="briefing-footer"><span>CYBER ORACLE · offline deterministic evaluation runtime</span><span>Generated for defender review</span></footer>
        </article>
      </main>
    </div>
  );
}