import { useState, useEffect, useRef, useCallback } from "react";
import { ShieldAlert, Zap, Radio, Square, TrendingUp } from "lucide-react";
import AppHeader from "@/components/AppHeader";
import { apiPost, apiGet } from "@/lib/api";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type SimulationResult = {
  risk: number;
  severity: string;
  features: Record<string, number>;
  pattern_risk?: number;
};

type PacketEvent = {
  id: string;
  timestamp: string;
  source: string;
  source_port: number;
  destination: string;
  destination_port: number;
  protocol: string;
  tcp_flags: string;
  packet_size: number | null;
  risk: number;
  severity: string;
  is_simulation?: boolean;
  is_campaign?: boolean;
  current_pps?: number;
  pattern_risk?: number;
};

type CampaignStatus = {
  running: boolean;
  elapsed: number;
  packets_sent: number;
  current_pps: number;
};

type PpsPoint = { t: string; pps: number };

const ATTACK_PRESETS: Record<
  string,
  { packetSize: number; tcpFlags: string; targetPort: number; description: string }
> = {
  "DDoS (Botnet Flood)": {
    packetSize: 65000,
    tcpFlags: "SYN",
    targetPort: 80,
    description: "Multi-source volumetric flood. Randomized botnet IPs per packet.",
  },
  "DoS (SYN Flood)": {
    packetSize: 60,
    tcpFlags: "SYN",
    targetPort: 80,
    description: "Single-source SYN flood exhausting TCP state tables.",
  },
  "Ransomware (SMB)": {
    packetSize: 1450,
    tcpFlags: "PSH|ACK",
    targetPort: 445,
    description: "Lateral movement via SMB. Credential brute-force pattern.",
  },
  "APT Exfil": {
    packetSize: 8000,
    tcpFlags: "ACK|URG",
    targetPort: 53,
    description: "Slow, stealthy exfiltration over DNS tunnel.",
  },
};

export default function Simulator() {
  const [attackType, setAttackType] = useState("DDoS (Botnet Flood)");
  const [targetIp, setTargetIp] = useState("10.0.0.1");
  const [targetPort, setTargetPort] = useState(80);
  const [packetSize, setPacketSize] = useState(65000);
  const [tcpFlags, setTcpFlags] = useState("SYN");
  const [durationSeconds, setDurationSeconds] = useState(30);
  const [maxPps, setMaxPps] = useState(20);

  const [result, setResult] = useState<SimulationResult | null>(null);
  const [campaignRunning, setCampaignRunning] = useState(false);
  const [campaignStatus, setCampaignStatus] = useState<CampaignStatus>({
    running: false,
    elapsed: 0,
    packets_sent: 0,
    current_pps: 0,
  });
  const [ppsHistory, setPpsHistory] = useState<PpsPoint[]>([]);
  const [events, setEvents] = useState<PacketEvent[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // WebSocket for live packet events
  useEffect(() => {
    const wsUrl =
      (window.location.protocol === "https:" ? "wss://" : "ws://") +
      window.location.host +
      "/api/live/stream";
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as PacketEvent;
        setEvents((prev) => [data, ...prev].slice(0, 100));
        // Track last ML result from simulated packets
        if (data.is_simulation && data.risk !== undefined) {
          setResult({
            risk: data.risk,
            severity: data.severity,
            features: data.features || {},
            pattern_risk: data.pattern_risk,
          });
        }
      } catch (e) {}
    };
    wsRef.current = ws;
    apiPost("/live/start", {}).catch(() => {});
    return () => ws.close();
  }, []);

  // Poll campaign status while running
  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const status = await apiGet<CampaignStatus>("/live/campaign/status");
        setCampaignStatus(status);
        setPpsHistory((prev) => {
          const point: PpsPoint = {
            t: `${Math.round(status.elapsed)}s`,
            pps: status.current_pps,
          };
          return [...prev, point].slice(-60); // keep last 60 data points
        });
        if (!status.running) {
          setCampaignRunning(false);
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch (e) {}
    }, 800);
  }, []);

  // Check if campaign is already running when tab is loaded (resumes state)
  useEffect(() => {
    apiGet<CampaignStatus>("/live/campaign/status").then((status) => {
      if (status.running) {
        setCampaignStatus(status);
        setCampaignRunning(true);
        startPolling();
      }
    }).catch(() => {});
  }, [startPolling]);

  const applyPreset = (type: string) => {
    setAttackType(type);
    const preset = ATTACK_PRESETS[type];
    if (preset) {
      setPacketSize(preset.packetSize);
      setTcpFlags(preset.tcpFlags);
      setTargetPort(preset.targetPort);
    }
  };

  const handleLaunchCampaign = async () => {
    setPpsHistory([]);
    setEvents([]);
    await apiPost("/live/campaign/start", {
      type: attackType,
      target_ip: targetIp,
      target_port: Number(targetPort),
      packet_size: Number(packetSize),
      tcp_flags: tcpFlags,
      duration_seconds: durationSeconds,
      max_pps: maxPps,
    });
    setCampaignRunning(true);
    startPolling();
  };

  const handleStopCampaign = async () => {
    await apiPost("/live/campaign/stop", {});
    setCampaignRunning(false);
    if (pollRef.current) clearInterval(pollRef.current);
    const status = await apiGet<CampaignStatus>("/live/campaign/status");
    setCampaignStatus(status);
  };

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const preset = ATTACK_PRESETS[attackType];

  return (
    <div className="app-shell">
      <AppHeader />
      <main className="sim-main">
        {/* Page header */}
        <div className="sim-page-header">
          <div>
            <div className="section-kicker">
              <span className="eyebrow-line" />
              ATTACK SIMULATOR
            </div>
            <h1>Campaign Simulator</h1>
            <p className="sim-subtitle">
              Launch a continuous attack campaign and watch packet flow escalate in real time — every
              packet scored by the live ML model.
            </p>
          </div>
        </div>

        <div className="sim-layout">
          {/* ── Left column: config ── */}
          <div className="sim-config-col">
            <div className="inspector-card sim-card">
              <h2 className="sim-card-title">ATTACK CONFIGURATION</h2>

              {/* Preset buttons */}
              <div className="sim-presets">
                {Object.keys(ATTACK_PRESETS).map((type) => (
                  <button
                    key={type}
                    className={`sim-preset-btn${attackType === type ? " sim-preset-btn--active" : ""}`}
                    onClick={() => applyPreset(type)}
                  >
                    {type}
                  </button>
                ))}
              </div>
              {preset && <p className="sim-preset-desc">{preset.description}</p>}

              {/* Fields */}
              <div className="sim-fields">
                <label className="sim-field">
                  <span>Target IP</span>
                  <input
                    value={targetIp}
                    onChange={(e) => setTargetIp(e.target.value)}
                    className="sim-input"
                  />
                </label>

                <div className="sim-field-row">
                  <label className="sim-field">
                    <span>Target Port</span>
                    <input
                      type="number"
                      value={targetPort}
                      onChange={(e) => setTargetPort(Number(e.target.value))}
                      className="sim-input"
                    />
                  </label>
                  <label className="sim-field">
                    <span>Packet Size (bytes)</span>
                    <input
                      type="number"
                      value={packetSize}
                      onChange={(e) => setPacketSize(Number(e.target.value))}
                      className="sim-input"
                    />
                  </label>
                </div>

                <label className="sim-field">
                  <span>TCP Flags</span>
                  <input
                    value={tcpFlags}
                    onChange={(e) => setTcpFlags(e.target.value)}
                    className="sim-input"
                  />
                </label>
              </div>

              {/* Campaign controls */}
              <div className="sim-campaign-controls">
                <h3 className="sim-card-title" style={{ marginBottom: "14px" }}>
                  CAMPAIGN SETTINGS
                </h3>
                <div className="sim-field-row">
                  <label className="sim-field">
                    <span>Duration (seconds)</span>
                    <input
                      type="number"
                      min={5}
                      max={120}
                      value={durationSeconds}
                      onChange={(e) => setDurationSeconds(Number(e.target.value))}
                      className="sim-input"
                    />
                  </label>
                  <label className="sim-field">
                    <span>Max PPS (peak rate)</span>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={maxPps}
                      onChange={(e) => setMaxPps(Number(e.target.value))}
                      className="sim-input"
                    />
                  </label>
                </div>

                {!campaignRunning ? (
                  <button className="run-button sim-launch-btn" onClick={handleLaunchCampaign}>
                    <Radio size={16} />
                    LAUNCH CAMPAIGN
                    <Zap size={14} />
                  </button>
                ) : (
                  <button
                    className="run-button sim-launch-btn sim-launch-btn--stop"
                    onClick={handleStopCampaign}
                  >
                    <Square size={14} fill="currentColor" />
                    STOP CAMPAIGN
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* ── Right column: live data ── */}
          <div className="sim-data-col">
            {/* Campaign status bar */}
            <div className={`inspector-card sim-card sim-status-bar${campaignRunning ? " sim-status-bar--active" : ""}`}>
              <div className="sim-status-row">
                <div className="sim-stat">
                  <span>STATUS</span>
                  <strong style={{ color: campaignRunning ? "var(--chart-1)" : undefined }}>
                    {campaignRunning ? "● RUNNING" : campaignStatus.packets_sent > 0 ? "COMPLETE" : "IDLE"}
                  </strong>
                </div>
                <div className="sim-stat">
                  <span>ELAPSED</span>
                  <strong>{campaignStatus.elapsed.toFixed(1)}s</strong>
                </div>
                <div className="sim-stat">
                  <span>PACKETS SENT</span>
                  <strong>{campaignStatus.packets_sent.toLocaleString()}</strong>
                </div>
                <div className="sim-stat">
                  <span>CURRENT PPS</span>
                  <strong style={{ color: "var(--chart-2, #00e5ff)" }}>
                    {campaignStatus.current_pps.toFixed(1)}
                  </strong>
                </div>
              </div>
            </div>

            {/* Live PPS chart */}
            <div className="inspector-card sim-card">
              <div className="sim-chart-header">
                <h3 className="sim-card-title">PACKETS PER SECOND — LIVE ESCALATION</h3>
                <TrendingUp size={14} style={{ opacity: 0.5 }} />
              </div>
              <div className="sim-chart-wrap">
                <ResponsiveContainer width="100%" height={180}>
                  <AreaChart
                    data={ppsHistory}
                    margin={{ top: 8, right: 8, left: -20, bottom: 0 }}
                  >
                    <defs>
                      <linearGradient id="ppsGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#e77969" stopOpacity={0.5} />
                        <stop offset="100%" stopColor="#e77969" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="#dce8df" strokeDasharray="2 5" vertical={false} />
                    <XAxis
                      dataKey="t"
                      tick={{ fill: "#75857d", fontSize: 9, fontFamily: "IBM Plex Mono" }}
                      tickLine={false}
                      axisLine={false}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      tick={{ fill: "#75857d", fontSize: 9, fontFamily: "IBM Plex Mono" }}
                      tickLine={false}
                      axisLine={false}
                      domain={[0, maxPps + 2]}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "#ffffff",
                        border: "1px solid #dce8df",
                        borderRadius: 6,
                        color: "#1f302c",
                        fontFamily: "IBM Plex Mono",
                        fontSize: 10,
                      }}
                      formatter={(value) => [`${value} pps`, "Packet rate"]}
                    />
                    <Area
                      type="monotone"
                      dataKey="pps"
                      stroke="#e77969"
                      strokeWidth={2}
                      fill="url(#ppsGradient)"
                      dot={false}
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
                {ppsHistory.length === 0 && (
                  <div className="sim-chart-empty">
                    Launch a campaign to see real-time packet rate escalation
                  </div>
                )}
              </div>
            </div>

            {/* Last ML evaluation */}
            <div className="inspector-card sim-card">
              <h3 className="sim-card-title">LAST ML EVALUATION</h3>
              {!result ? (
                <div className="sim-empty">Launch a campaign to see ML scoring.</div>
              ) : (
                <div className="sim-result">
                  <div className="sim-result-main" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "16px" }}>
                    <div>
                      <div className="sim-result-label">CURRENT FLOW RISK</div>
                      <div
                        className="sim-result-score"
                        style={{ color: result.risk > 0.6 ? "var(--chart-1)" : undefined }}
                      >
                        {(result.risk * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div>
                      <div className="sim-result-label">PATTERN FORECAST</div>
                      <div
                        className="sim-result-score"
                        style={{ color: (result.pattern_risk ?? 0) > 0.6 ? "var(--chart-1)" : "var(--chart-2, #00e5ff)" }}
                        title="Sequence model prediction based on recent flow history"
                      >
                        {result.pattern_risk !== undefined ? (result.pattern_risk * 100).toFixed(1) + "%" : "—"}
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div className="sim-result-label">SEVERITY</div>
                      <div
                        className="sim-result-severity"
                        style={{ color: result.risk > 0.6 || (result.pattern_risk ?? 0) > 0.6 ? "var(--chart-1)" : undefined, fontSize: "16px" }}
                      >
                        {result.severity}
                      </div>
                    </div>
                  </div>
                  <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid var(--border)" }}>
                     <div className="sim-result-label" style={{ marginBottom: "8px" }}>SHAP ATTRIBUTIONS (Top 3)</div>
                     {Object.entries(result.features).sort((a,b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0,3).map(([feature, weight]) => (
                        <div key={feature} style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "4px" }}>
                           <span style={{ fontFamily: "IBM Plex Mono" }}>{feature}</span>
                           <strong style={{ color: weight > 0 ? "var(--chart-1)" : "#3b82f6" }}>
                              {weight > 0 ? "+" : ""}{(weight * 100).toFixed(1)}%
                           </strong>
                        </div>
                     ))}
                  </div>
                </div>
              )}
            </div>

            {/* Live traffic feed */}
            <div className="inspector-card sim-card">
              <h3 className="sim-card-title">LIVE PACKET STREAM (ML SCORED)</h3>
              <div className="sim-table-wrap">
                <table className="sim-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Source</th>
                      <th>Destination</th>
                      <th>PPS</th>
                      <th>Risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="sim-table-empty">
                          Waiting for traffic…
                        </td>
                      </tr>
                    ) : (
                      events.map((ev) => (
                        <tr
                          key={ev.id}
                          style={{
                            background: ev.is_campaign
                              ? "rgba(231,121,105,0.12)"
                              : ev.is_simulation
                                ? "rgba(255, 200, 0, 0.1)"
                                : "transparent",
                            color: ev.risk > 0.6 ? "var(--chart-1)" : undefined,
                          }}
                        >
                          <td>{new Date(ev.timestamp).toLocaleTimeString()}</td>
                          <td>{ev.source}:{ev.source_port}</td>
                          <td>{ev.destination}:{ev.destination_port}</td>
                          <td>{ev.current_pps ? `${ev.current_pps} pps` : "—"}</td>
                          <td style={{ fontWeight: "bold" }}>
                            {ev.is_campaign && (
                              <ShieldAlert
                                size={10}
                                style={{ display: "inline", marginRight: "2px" }}
                              />
                            )}
                            {(ev.risk * 100).toFixed(1)}%
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
