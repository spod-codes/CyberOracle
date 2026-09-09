import { useState, useEffect, useRef } from "react";
import { Play, Square, ShieldAlert, TrendingUp } from "lucide-react";
import AppHeader from "@/components/AppHeader";
import { Button } from "@/components/ui/button";
import { apiPost } from "@/lib/api";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type PacketEvent = {
  id: string;
  timestamp: string;
  source: string;
  source_port: number;
  destination: string;
  destination_port: number;
  protocol: string;
  tcp_flags: string;
  risk: number;
  severity: string;
  is_simulation?: boolean;
  is_campaign?: boolean;
};

type RiskPoint = { t: string; risk: number };

export default function LiveMonitor() {
  const [events, setEvents] = useState<PacketEvent[]>([]);
  const [capturing, setCapturing] = useState(false);
  const [riskHistory, setRiskHistory] = useState<RiskPoint[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const counterRef = useRef(0);

  useEffect(() => {
    const baseApiUrl = import.meta.env.VITE_API_URL || "";
    const wsUrl = baseApiUrl
      ? baseApiUrl.replace(/^http/, "ws") + "/live/stream"
      : (window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host + "/api/live/stream";
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as PacketEvent;
        setEvents((prev) => [data, ...prev].slice(0, 100));
        // Record a risk data point every ~5 events for a smooth trend
        counterRef.current += 1;
        if (counterRef.current % 3 === 0) {
          setRiskHistory((prev) => [
            ...prev,
            { t: new Date(data.timestamp).toLocaleTimeString(), risk: Math.round(data.risk * 100) },
          ].slice(-60));
        }
      } catch (e) {}
    };
    wsRef.current = ws;

    // Recover capture state if it was already running in background
    import("@/lib/api").then(({ apiGet }) => {
      apiGet<{ capturing: boolean }>("/live/status").then((status) => {
        if (status.capturing) setCapturing(true);
      }).catch(() => {});
    });

    return () => ws.close();
  }, []);

  const toggleCapture = async () => {
    if (capturing) {
      await apiPost("/live/stop", {});
      setCapturing(false);
    } else {
      await apiPost("/live/start", {});
      setCapturing(true);
    }
  };

  const highRiskCount = events.filter((e) => e.risk > 0.6).length;
  const avgRisk =
    events.length > 0
      ? ((events.reduce((acc, e) => acc + e.risk, 0) / events.length) * 100).toFixed(1)
      : "0.0";
  const campaignPackets = events.filter((e) => e.is_campaign).length;

  return (
    <div className="app-shell">
      <AppHeader />
      <main className="live-main">
        {/* Page header */}
        <div className="live-header">
          <div>
            <div className="section-kicker">
              <span className="eyebrow-line" />
              LIVE INTELLIGENCE
            </div>
            <h1>Real-time Network Monitor</h1>
            <p className="live-subtitle">
              Local packet connections captured by{" "}
              <code>psutil</code> and scored live by the RandomForest model.
            </p>
          </div>
          <Button
            onClick={toggleCapture}
            variant={capturing ? "destructive" : "default"}
            className="live-toggle-btn"
          >
            {capturing ? <Square size={16} /> : <Play size={16} />}
            {capturing ? "STOP CAPTURE" : "START LOCAL CAPTURE"}
          </Button>
        </div>

        {/* Stats ribbon */}
        <div className="live-ribbon">
          <div className="live-stat">
            <span className="metric-overline">PACKETS SEEN (LAST 100)</span>
            <strong>{events.length}</strong>
            <small>events in buffer</small>
          </div>
          <div className="live-stat">
            <span className="metric-overline">HIGH RISK EVENTS</span>
            <strong style={{ color: highRiskCount > 0 ? "var(--chart-1)" : undefined }}>
              {highRiskCount}
            </strong>
            <small>risk &gt; 60%</small>
          </div>
          <div className="live-stat">
            <span className="metric-overline">AVERAGE RISK</span>
            <strong>{avgRisk}%</strong>
            <small>across all captured</small>
          </div>
          <div className="live-stat">
            <span className="metric-overline">CAMPAIGN PACKETS</span>
            <strong style={{ color: campaignPackets > 0 ? "#e77969" : undefined }}>
              {campaignPackets}
            </strong>
            <small>simulated in this session</small>
          </div>
        </div>

        {/* Risk trend chart */}
        <div className="inspector-card live-card">
          <div className="live-card-header">
            <h3 className="sim-card-title">LIVE RISK TREND</h3>
            <TrendingUp size={14} style={{ opacity: 0.5 }} />
          </div>
          <div className="sim-chart-wrap">
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart
                data={riskHistory}
                margin={{ top: 8, right: 8, left: -20, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="riskTrendGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#e77969" stopOpacity={0.45} />
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
                  domain={[0, 100]}
                  tick={{ fill: "#75857d", fontSize: 9, fontFamily: "IBM Plex Mono" }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v) => `${v}%`}
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
                  formatter={(v) => [`${v}%`, "Risk score"]}
                />
                <Area
                  type="monotone"
                  dataKey="risk"
                  stroke="#e77969"
                  strokeWidth={2}
                  fill="url(#riskTrendGrad)"
                  dot={false}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
            {riskHistory.length === 0 && (
              <div className="sim-chart-empty">Start capture to see real-time risk trend</div>
            )}
          </div>
        </div>

        {/* Live packet stream table */}
        <div className="inspector-card live-card">
          <h3 className="sim-card-title" style={{ marginBottom: "16px" }}>
            LIVE PACKET STREAM
          </h3>
          <div style={{ overflowX: "auto" }}>
            <table className="flow-table">
              <thead>
                <tr>
                  <th>TIME</th>
                  <th>SOURCE</th>
                  <th>DESTINATION</th>
                  <th>PROTOCOL</th>
                  <th>FLAGS</th>
                  <th>RISK</th>
                </tr>
              </thead>
              <tbody>
                {events.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ padding: "24px", textAlign: "center", opacity: 0.5 }}>
                      No events captured yet. Start capture or launch a simulator campaign.
                    </td>
                  </tr>
                ) : (
                  events.map((ev) => (
                    <tr
                      key={ev.id}
                      style={{
                        background: ev.is_campaign
                          ? "rgba(231,121,105,0.1)"
                          : ev.is_simulation
                            ? "rgba(255,200,0,0.08)"
                            : "transparent",
                        color: ev.risk > 0.6 ? "var(--chart-1)" : undefined,
                      }}
                    >
                      <td>{new Date(ev.timestamp).toLocaleTimeString()}</td>
                      <td>{ev.source}:{ev.source_port}</td>
                      <td>{ev.destination}:{ev.destination_port}</td>
                      <td><span className="protocol-tag">{ev.protocol}</span></td>
                      <td className="mono-cell">{ev.tcp_flags || "—"}</td>
                      <td style={{ fontWeight: "bold" }}>
                        {ev.is_campaign && (
                          <ShieldAlert size={12} style={{ display: "inline", marginRight: "4px" }} />
                        )}
                        {(ev.risk * 100).toFixed(1)}%{" "}
                        <small style={{ fontWeight: "normal" }}>({ev.severity})</small>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
