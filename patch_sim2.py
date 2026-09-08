
import sys

with open("frontend/src/pages/Simulator.tsx", "r", encoding="utf-8") as f:
    content = f.read()

old_state = """export default function Simulator() {
  const [attackType, setAttackType] = useState("DDoS");
  const [targetIp, setTargetIp] = useState("10.0.0.1");
  const [targetPort, setTargetPort] = useState(80);
  const [sourcePort, setSourcePort] = useState(44332);
  const [packetSize, setPacketSize] = useState(65000);
  const [tcpFlags, setTcpFlags] = useState("SYN|RST|URG");
  
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [history, setHistory] = useState<{type: string, risk: number, time: string}[]>([]);
  const [loading, setLoading] = useState(false);"""

new_state = """type PacketEvent = {
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
  const [history, setHistory] = useState<{type: string, risk: number, time: string}[]>([]);
  const [loading, setLoading] = useState(false);
  
  const [events, setEvents] = useState<PacketEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const wsUrl = window.location.protocol === "https:" ? "wss://" : "ws://" + window.location.host + "/api/live/stream";
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as PacketEvent;
        setEvents((prev) => [data, ...prev].slice(0, 20));
      } catch (e) {}
    };
    wsRef.current = ws;
    
    // Auto-start capture for demonstration
    apiPost("/live/start", {}).catch(() => {});
    
    return () => ws.close();
  }, []);"""

content = content.replace(old_state, new_state)

old_table = """            <div className="inspector-card" style={{ padding: "24px" }}>
              <h3 style={{ fontSize: "12px", opacity: 0.6, marginBottom: "16px" }}>INJECTION HISTORY</h3>
              {history.length === 0 ? <div style={{ opacity: 0.5, fontSize: "13px" }}>No history yet.</div> : (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {history.map((h, i) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: "13px", padding: "8px", background: "rgba(255,255,255,0.02)", borderRadius: "4px" }}>
                      <span>{h.time} ? <strong>{h.type}</strong></span>
                      <span style={{ color: h.risk > 0.6 ? "var(--chart-1)" : "inherit" }}>{(h.risk * 100).toFixed(1)}%</span>
                    </div>
                  ))}
                </div>
              )}
            </div>"""

new_table = """            <div className="inspector-card" style={{ padding: "24px" }}>
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
            </div>"""

content = content.replace(old_table, new_table)

with open("frontend/src/pages/Simulator.tsx", "w", encoding="utf-8") as f:
    f.write(content)
print("done")

