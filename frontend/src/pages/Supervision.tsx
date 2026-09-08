import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Check, Download, Laptop, RefreshCw, ShieldCheck, Sparkles, X } from "lucide-react";
import { toast } from "sonner";

import AppHeader from "@/components/AppHeader";
import { Button } from "@/components/ui/button";
import { apiGet, apiPost, apiDelete } from "@/lib/api";
import type { AgentEnrollment, AgentSummary, ModelContext, ModelProposal, SupervisionSummary } from "@/lib/types";

function formatBytes(value: number) {
  if (value === 0) return "0 B";
  const k = 1024, sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(value) / Math.log(k));
  return parseFloat((value / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

export default function Supervision() {
  const queryClient = useQueryClient();
  const [agentName, setAgentName] = useState("Primary Remote Sensor");
  const [enrollment, setEnrollment] = useState<AgentEnrollment | null>(null);
  const summary = useQuery({ queryKey: ["supervision-summary"], queryFn: () => apiGet<SupervisionSummary>("/supervision/summary"), refetchInterval: 2500, retry: false });
  const agents = useQuery({ queryKey: ["supervision-agents"], queryFn: () => apiGet<AgentSummary[]>("/supervision/agents"), refetchInterval: 5000, retry: false });
  const proposals = useQuery({ queryKey: ["model-proposals"], queryFn: () => apiGet<ModelProposal[]>("/supervision/proposals"), refetchInterval: 5000, retry: false });
  const context = useQuery({ queryKey: ["model-context"], queryFn: () => apiGet<ModelContext>("/supervision/context"), retry: false });
  const enrollMutation = useMutation({ mutationFn: () => apiPost<AgentEnrollment>("/supervision/agents", { name: agentName }), onSuccess: (data) => { setEnrollment(data); void queryClient.invalidateQueries({ queryKey: ["supervision-agents"] }); toast.success("Capture agent enrolled"); } });
  const generateMutation = useMutation({ mutationFn: () => apiPost<ModelProposal[]>("/supervision/proposals/generate", {}), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["model-proposals"] }) });
  const decisionMutation = useMutation({ mutationFn: ({ id, approved }: { id: string; approved: boolean }) => apiPost<ModelProposal>(`/supervision/proposals/${id}/decision`, { approved }), onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["model-proposals"] }); void queryClient.invalidateQueries({ queryKey: ["model-context"] }); } });
  const deleteAgentMutation = useMutation({ mutationFn: (id: string) => apiDelete(`/supervision/agents/${id}`), onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["supervision-agents"] }); toast.success("Agent disconnected and data cleared."); } });

  const data = summary.data;
  const downloadAgent = () => {
    if (!enrollment) return;
    const url = `${enrollment.download_path}?token=${encodeURIComponent(enrollment.token)}&base_url=${encodeURIComponent(window.location.origin)}`;
    window.location.href = url;
  };

  return <div className="app-shell" data-testid="supervision-page"><AppHeader /><main className="supervision-main"><section className="supervision-hero"><div><div className="eyebrow"><span className="eyebrow-line" /> REAL-TIME SUPERVISION / SERVER RUNTIME</div><h1>Watch the network evolve.</h1><p>A privileged local agent sends packet metadata only—addresses, ports, flags, timing, and sizes. Payload contents are discarded before upload.</p></div><div className="supervision-mode"><span className={data?.active_agents ? "status-dot" : "status-dot status-dot-offline"} /><strong>{data?.active_agents ? "LIVE AGENT CONNECTED" : "WAITING FOR AGENT"}</strong><small>{data?.retention_days ?? 7}-day rolling retention · {data?.capture_mode === "agent-packet-metadata" ? "no payload storage" : (data?.capture_mode ?? "no payload storage")}</small></div></section>
    <section className="supervision-stats"><div><span>LIVE AGENTS</span><strong>{data?.active_agents ?? 0} / {data?.total_agents ?? 0}</strong><small>reporting in last 30 seconds</small></div><div><span>PACKETS · 24H</span><strong>{(data?.packets_24h ?? 0).toLocaleString()}</strong><small>{formatBytes(data?.bytes_24h ?? 0)} metadata volume</small></div><div><span>HIGH RISK</span><strong>{data?.high_risk_24h ?? 0}</strong><small>events above 62%</small></div><div><span>MODEL CONTEXT</span><strong>{(context.data?.risk_multiplier ?? 1).toFixed(2)}×</strong><small>analyst-approved sensitivity</small></div></section>
    <section className="supervision-grid"><div className="agent-panel"><div className="panel-heading"><div><div className="section-kicker"><span>01</span> CAPTURE AGENTS</div><h2>Connect a Remote Sensor</h2></div><Laptop size={20} /></div><p className="panel-help">Download and run the python agent script (Linux/Mac/Windows) on the device you want to supervise. The agent captures packet metadata and streams it directly to this dashboard.</p><div className="agent-enroll"><input value={agentName} onChange={(event) => setAgentName(event.target.value)} data-testid="agent-name-input" /><Button onClick={() => enrollMutation.mutate()} disabled={!agentName.trim() || enrollMutation.isPending} data-testid="enroll-agent-button"><ShieldCheck size={14} /> enroll agent</Button>{enrollment && <Button variant="outline" onClick={downloadAgent} data-testid="download-agent-button"><Download size={14} /> download .py</Button>}</div>
    <div style={{ marginTop: "14px", borderTop: "1px solid var(--border-color)", paddingTop: "14px" }}>
        <p className="panel-help" style={{ marginBottom: "12px" }}>Alternatively, auto-feed real network connections directly from this machine to bypass the python script requirement.</p>
        <div style={{ display: "flex", gap: "8px" }}>
            <Button className="run-button" onClick={() => { apiPost("/supervision/local-capture", {}); toast.success("Local background feed started!"); }}><Activity size={14} /> START LOCAL CAPTURE FEED</Button>
            <Button variant="outline" onClick={() => { apiPost("/supervision/local-capture/stop", {}); toast.success("Local feed stopped."); }}><X size={14} /> STOP</Button>
        </div>
    </div>
    <div className="agent-list">{agents.data?.length ? agents.data.map((agent) => <div key={agent.id}><span className={agent.status === "Live" ? "agent-live" : "agent-offline"}><i /> {agent.status}</span><strong>{agent.name}</strong><small>{agent.packets_ingested.toLocaleString()} packets · {agent.last_seen ? `seen ${new Date(agent.last_seen).toLocaleTimeString()}` : "never connected"}</small><button onClick={() => deleteAgentMutation.mutate(agent.id)} title="Disconnect & Delete Agent" className="icon-button" style={{ marginLeft: "auto", color: "var(--critical-color)" }}><X size={14} /></button></div>) : <p>No capture agents enrolled yet.</p>}</div></div>
    <div className="iteration-panel"><div className="panel-heading"><div><div className="section-kicker"><span>02</span> SELF-ITERATION CONTROL</div><h2>Review proposed model changes</h2></div><button className="icon-button" onClick={() => generateMutation.mutate()} data-testid="generate-proposal-button" title="Analyze recent context"><RefreshCw size={15} /></button></div><p className="panel-help">Cyber Oracle studies recent metadata and proposes sensitivity changes. Nothing changes until an analyst approves it.</p><div className="proposal-list">{proposals.data?.length ? proposals.data.map((proposal) => <div className="proposal-card" key={proposal.id} data-testid={`model-proposal-${proposal.id}`}><div><span className={`proposal-status proposal-${proposal.status.toLowerCase()}`}>{proposal.status}</span><strong>{proposal.title}</strong><p>{proposal.rationale}</p><small>{proposal.current_value.toFixed(3)} → {proposal.proposed_value.toFixed(3)} · {proposal.evidence_events} events</small></div>{proposal.status === "Pending" && <div><button onClick={() => decisionMutation.mutate({ id: proposal.id, approved: true })} data-testid={`approve-proposal-${proposal.id}`}><Check size={13} /> approve</button><button onClick={() => decisionMutation.mutate({ id: proposal.id, approved: false })} data-testid={`reject-proposal-${proposal.id}`}><X size={13} /> reject</button></div>}</div>) : <div className="empty-supervision"><Sparkles size={18} /><span>No proposal yet</span><small>At least 8 live metadata events are needed.</small></div>}</div></div></section>
    <section className="live-traffic-panel"><div className="panel-heading"><div><div className="section-kicker"><span>03</span> LIVE PACKET METADATA</div><h2>Recent server-runtime observations</h2></div><span className="capture-disclaimer"><Activity size={14} /> agent capture only</span></div><div className="live-table-wrap"><table><thead><tr><th>TIME</th><th>SOURCE → DESTINATION</th><th>PROTOCOL</th><th>FLAGS</th><th>SIZE</th><th>RISK</th></tr></thead><tbody>{data?.recent_events.length ? data.recent_events.map((event) => <tr key={event.id}><td>{new Date(event.timestamp).toLocaleTimeString()}</td><td><strong>{event.source}{event.source_port ? `:${event.source_port}` : ""}</strong><small>→ {event.destination}{event.destination_port ? `:${event.destination_port}` : ""}</small></td><td>{event.protocol}</td><td>{event.tcp_flags || "—"}</td><td>{formatBytes(event.packet_size)}</td><td><span className={`live-risk risk-${event.severity.toLowerCase()}`}>{Math.round(event.risk * 100)}%</span></td></tr>) : <tr><td colSpan={6}><div className="empty-supervision"><Activity size={18} /><span>No live metadata received</span><small>Enroll and run the local capture agent to begin.</small></div></td></tr>}</tbody></table></div></section>
  </main></div>;
}