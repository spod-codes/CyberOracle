
import sys

with open("frontend/src/pages/Simulator.tsx", "r", encoding="utf-8") as f:
    content = f.read()

start_marker = "<h3 style={{ fontSize: \"12px\", opacity: 0.6, marginBottom: \"16px\" }}>INJECTION HISTORY</h3>"

if start_marker in content:
    start_idx = content.find(start_marker)
    # find the end of the div containing INJECTION HISTORY.
    # It ends with </div>\n          </div>\n        </div>\n      </main>
    # So we just cut it out
    
    end_marker = "</div>\n          </div>\n        </div>\n      </main>"
    end_idx = content.find(end_marker)
    
    new_table = """<h3 style={{ fontSize: "12px", opacity: 0.6, marginBottom: "16px" }}>LIVE NETWORK TRAFFIC (ML SCORED)</h3>
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
"""
    content = content[:start_idx] + new_table + content[end_idx:]

with open("frontend/src/pages/Simulator.tsx", "w", encoding="utf-8") as f:
    f.write(content)
print("done")

