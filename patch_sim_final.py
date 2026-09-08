
import sys

full_code = """import { useState, useEffect, useRef } from "react";
import { ShieldAlert, Zap } from "lucide-react";
import AppHeader from "@/components/AppHeader";
import { Button } from "@/components/ui/button";
import { apiPost } from "@/lib/api";

type SimulationResult = {
  risk: number;
  severity: string;
  features: Record<string, number>;
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
  packet_size: number;
  risk: number;
  severity: string;
  is_simulation?: boolean;
};

export default function Simulator() {
  const [attackType, setAttackType] = useState("DDoS");
  const [targetIp, setTargetIp] = useState("10.0.0.1");
  const [targetPort, setTargetPort] = useState(80);
  const [sourcePort, setSourcePort] = useState(44332);
  const [packetSize, setPacketSize] = useState(65000);
  const [tcpFlags, setTcpFlags] = useState("SYN|RST|URG");
  
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);
  
  const [events, setEvents] = useState<PacketEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const wsUrl = window.location.protocol === "https:" ? "wss://" : "ws://" + window.location.host + "/api/live/stream";
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as PacketEvent;
        setEvents((prev) => [data, ...prev].slice(0, 50));
      } catch (e) {}
    };
    wsRef.current = ws;
    
    // Auto-start capture for demonstration
    apiPost("/live/start", {}).catch(() => {});
    
    return () => ws.close();
  }, []);

  const applyPreset = (type: string) => {
    setAttackType(type);
    if (type === "DDoS") {
      setPacketSize(65000);
      setTcpFlags("SYN");
      setTargetPort(80);
    } else if (type === "Ransomware (SMB)") {
      setPacketSize(1450);
      setTcpFlags("PSH|ACK");
      setTargetPort(445);
    } else if (type === "APT Exfil") {
      setPacketSize(8000);
      setTcpFlags("ACK|URG");
      setTargetPort(53);
    }
  };

  const handleInject = async () => {
    setLoading(true);
    try {
      const res = await apiPost<{risk: number, severity: string, features: Record<string, number>}>("/live/inject", {
        type: attackType,
        target_ip: targetIp,
        target_port: Number(targetPort),
        source_port: Number(sourcePort),
        packet_size: Number(packetSize),
        tcp_flags: tcpFlags
      });
      setResult(res);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  return (
    <div className="app-shell">
      <AppHeader />
      <main className="dashboard-main" style={{ padding: "40px" }}>
        <div style={{ marginBottom: "32px" }}>
          <h1 style={{ fontSize: "32px", fontWeight: "bold" }}>Attack Simulator</h1>
          <p style={{ opacity: 0.7 }}>Craft a packet and instantly evaluate it through the ML model.</p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "32px" }}>
          <div className="inspector-card" style={{ padding: "32px" }}>
            <h2 style={{ fontSize: "16px", marginBottom: "24px", fontWeight: "bold" }}>ATTACK CONFIGURATION</h2>
            
            <div style={{ display: "flex", gap: "8px", marginBottom: "24px" }}>
              <Button variant={attackType === "DDoS" ? "default" : "outline"} onClick={() => applyPreset("DDoS")} size="sm">DDoS</Button>
              <Button variant={attackType === "Ransomware (SMB)" ? "default" : "outline"} onClick={() => applyPreset("Ransomware (SMB)")} size="sm">Ransomware</Button>
              <Button variant={attackType === "APT Exfil" ? "default" : "outline"} onClick={() => applyPreset("APT Exfil")} size="sm">APT Exfil</Button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <label>
                <div style={{ fontSize: "12px", opacity: 0.6, marginBottom: "4px" }}>Target IP</div>
                <input value={targetIp} onChange={e => setTargetIp(e.target.value)} style={{ width: "100%", padding: "8px", background: "rgba(0,0,0,0.2)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "4px", color: "white" }} />
              </label>
              
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <label>
                  <div style={{ fontSize: "12px", opacity: 0.6, marginBottom: "4px" }}>Target Port</div>
                  <input type="number" value={targetPort} onChange={e => setTargetPort(Number(e.target.value))} style={{ width: "100%", padding: "8px", background: "rgba(0,0,0,0.2)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "4px", color: "white" }} />
                </label>
                <label>
                  <div style={{ fontSize: "12px", opacity: 0.6, marginBottom: "4px" }}>Source Port</div>
                  <input type="number" value={sourcePort} onChange={e => setSourcePort(Number(e.target.value))} style={{ width: "100%", padding: "8px", background: "rgba(0,0,0,0.2)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "4px", color: "white" }} />
                </label>
              </div>

              <label>
                <div style={{ fontSize: "12px", opacity: 0.6, marginBottom: "4px" }}>Packet Size (Bytes)</div>
                <input type="number" value={packetSize} onChange={e => setPacketSize(Number(e.target.value))} style={{ width: "100%", padding: "8px", background: "rgba(0,0,0,0.2)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "4px", color: "white" }} />
              </label>

              <label>
                <div style={{ fontSize: "12px", opacity: 0.6, marginBottom: "4px" }}>TCP Flags</div>
                <input value={tcpFlags} onChange={e => setTcpFlags(e.target.value)} style={{ width: "100%", padding: "8px", background: "rgba(0,0,0,0.2)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "4px", color: "white" }} />
              </label>
            </div>

            <Button onClick={handleInject} disabled={loading} style={{ width: "100%", marginTop: "32px", gap: "8px" }}>
              <Zap size={16} /> INJECT ATTACK
            </Button>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            <div className="inspector-card" style={{ padding: "32px", flex: 1 }}>
              <h2 style={{ fontSize: "16px", marginBottom: "24px", fontWeight: "bold" }}>ML EVALUATION</h2>
              
              {!result ? (
                <div style={{ opacity: 0.5, textAlign: "center", padding: "40px 0" }}>Inject an attack to see ML scoring.</div>
              ) : (
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: "32px" }}>
                    <div>
                      <div style={{ fontSize: "12px", opacity: 0.6, marginBottom: "4px" }}>PREDICTED RISK</div>
                      <div style={{ fontSize: "48px", fontWeight: "bold", lineHeight: 1, color: result.risk > 0.6 ? "var(--chart-1)" : "inherit" }}>
                        {(result.risk * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: "12px", opacity: 0.6, marginBottom: "4px" }}>SEVERITY</div>
                      <div style={{ fontSize: "24px", fontWeight: "bold", color: result.risk > 0.6 ? "var(--chart-1)" : "inherit" }}>{result.severity}</div>
                    </div>
                  </div>

                  <h3 style={{ fontSize: "12px", opacity: 0.6, marginBottom: "12px" }}>SHAP FEATURE ATTRIBUTION (EST)</h3>
                  {Object.entries(result.features).map(([feat, val]) => (
                    <div key={feat} style={{ marginBottom: "12px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", marginBottom: "4px" }}>
                        <span>{feat}</span>
                        <span style={{ fontWeight: "bold" }}>+{val.toFixed(3)}</span>
                      </div>
                      <div style={{ width: "100%", height: "6px", background: "rgba(255,255,255,0.1)", borderRadius: "3px" }}>
                        <div style={{ height: "100%", width: `${Math.min(100, val * 200)}%`, background: "var(--chart-1)", borderRadius: "3px" }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="inspector-card" style={{ padding: "24px" }}>
              <h3 style={{ fontSize: "12px", opacity: 0.6, marginBottom: "16px" }}>LIVE NETWORK TRAFFIC (ML SCORED)</h3>
              <div style={{ overflowY: "auto", maxHeight: "300px" }}>
                <table style={{ width: "100%", textAlign: "left", fontSize: "12px" }}>
                  <thead>
                    <tr style={{ opacity: 0.5, borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                      <th style={{ padding: "4px" }}>Time</th>
                      <th style={{ padding: "4px" }}>Source</th>
                      <th style={{ padding: "4px" }}>Dest</th>
                      <th style={{ padding: "4px" }}>Risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.length === 0 ? (
                      <tr><td colSpan={4} style={{ padding: "16px", textAlign: "center", opacity: 0.5 }}>Waiting for live traffic...</td></tr>
                    ) : (
                      events.map(ev => (
                        <tr key={ev.id} style={{ 
                          background: ev.is_simulation ? "rgba(255, 200, 0, 0.15)" : (ev.risk > 0.6 ? "rgba(255, 50, 50, 0.15)" : "transparent"),
                          color: ev.risk > 0.6 ? "var(--chart-1)" : (ev.is_simulation ? "#ffc800" : "inherit"),
                          transition: "background 0.5s ease"
                        }}>
                          <td style={{ padding: "4px" }}>{new Date(ev.timestamp).toLocaleTimeString()}</td>
                          <td style={{ padding: "4px" }}>{ev.source}:{ev.source_port}</td>
                          <td style={{ padding: "4px" }}>{ev.destination}:{ev.destination_port}</td>
                          <td style={{ padding: "4px", fontWeight: "bold" }}>
                            {ev.is_simulation && <ShieldAlert size={10} style={{display:"inline", marginRight:"2px"}} />}
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
"""

with open("frontend/src/pages/Simulator.tsx", "w", encoding="utf-8") as f:
    f.write(full_code)
print("done")

