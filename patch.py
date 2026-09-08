import sys

with open("frontend/src/pages/Home.tsx", "r") as f:
    content = f.read()

# Replace Hero
old_hero = """        <div className="landing-art-backdrop" data-testid="threat-identity-artwork" aria-hidden="true"><img src={THREAT_ART_URL} alt="" /><span /></div>
        <section className="ingest-hero" data-testid="ingestion-hero">
          <div className="hero-copy">
            <div className="eyebrow" title="A model that learns how network behavior changes over time and predicts what may happen next."><span className="eyebrow-line" /> THREAT INTELLIGENCE / EVALUATION BAY</div>
            <h1 style={{ fontSize: "clamp(52px, 8vw, 96px)", letterSpacing: "-0.07em", lineHeight: 0.90, fontWeight: 800 }}><span style={{ display: "block" }}>CYBER</span><em style={{ display: "block" }}>ORACLE</em></h1>
            <p>Real-time network threat detection powered by a <strong>RandomForest ML model</strong> trained on 200,000 labeled attack vectors from CIC-IDS 2018 &amp; CTU-13.</p>
            <div className="hero-meta"><span><CheckCircle2 size={14} /> 99.9% accuracy · no cloud dependency</span><span><Layers3 size={14} /> RandomForest + ExponentialSmoothing</span><span><Sparkles size={14} /> SHAP-based explainability</span></div>
          </div>
        </section>"""

new_hero = """        <section className="ingest-hero" data-testid="ingestion-hero" style={{ display: "flex", position: "relative", overflow: "hidden", minHeight: "500px", background: "var(--background)", color: "var(--foreground)", marginBottom: "40px", borderRadius: "16px", border: "2px solid var(--border)", boxShadow: "0 20px 40px rgba(0,0,0,0.1)" }}>
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
        </section>"""

# Replace config panel
old_config = """            <div className="section-kicker" title="Configure the RandomForest ML pipeline parameters."><span>02</span> ML PIPELINE CONFIGURATION</div>
            <div className="config-panel" data-testid="rollout-configuration">
              <div className="config-panel-top"><div><h2>Configure the pipeline</h2><p>Tune how the RandomForest model evaluates and forecasts threat stages.</p></div><span className="config-chip"><span className="status-dot" /> OFFLINE · Local Model</span></div>
              <div className="form-grid">
                <label className="field-label">ATTACK SIMULATION<select value={architecture} onChange={(event) => setArchitecture(event.target.value)} data-testid="architecture-select"><option>DDoS / Volumetric</option><option>Ransomware / Lateral Move</option><option>APT / Exfiltration</option><option>Botnet / C2</option></select></label>
                <label className="field-label">EXPLAINABILITY<select value={explainability} onChange={(event) => setExplainability(event.target.value)} data-testid="explainability-select"><option>SHAP Feature Attribution</option><option>Surrogate Decision Tree</option></select></label>
                <label className="field-label">FORECAST HORIZON<select value={horizon} onChange={(event) => setHorizon(event.target.value)} data-testid="horizon-select"><option value="5">K = 5 windows</option><option value="8">K = 8 windows</option><option value="12">K = 12 windows</option><option value="20">K = 20 windows</option></select></label>
                <label className="field-label">FEATURE WINDOW<select value={windowSize} onChange={(event) => setWindowSize(event.target.value)} data-testid="window-size-select"><option value="25">25 rows / state</option><option value="50">50 rows / state</option><option value="100">100 rows / state</option><option value="250">250 rows / state</option></select></label>
              </div>
              <div className="pipeline-row" data-testid="inference-pipeline"><span className="pipeline-step pipeline-step-active"><span>01</span> normalize</span><span className="pipeline-arrow">?</span><span className="pipeline-step"><span>02</span> RandomForest</span><span className="pipeline-arrow">?</span><span className="pipeline-step"><span>03</span> ExpSmoothing</span><span className="pipeline-arrow">?</span><span className="pipeline-step"><span>04</span> SHAP explain</span></div>
              <Button className="run-button" disabled={!file || !inspection?.rows || runMutation.isPending} onClick={() => file && runMutation.mutate(file)} data-testid="run-inference-button"><Play size={17} fill="currentColor" /> {runMutation.isPending ? "RUNNING ML PIPELINE…" : "RUN ML THREAT ANALYSIS"}<ArrowRight size={17} /></Button>
              {runMutation.isError && <p className="inline-error" data-testid="inference-error">{formatError(runMutation.error)}</p>}
              <p className="config-footnote"><Clock3 size={13} /> Typical runtime &lt; 2 seconds · RandomForestClassifier trained on 200k real attack vectors</p>
            </div>"""

new_config = """            <div className="section-kicker" title="Configure the world model transition dynamics."><span>02</span> WORLD MODEL CONFIGURATION</div>
            <div className="config-panel" data-testid="rollout-configuration" style={{ background: "var(--card)", border: "2px solid var(--border)", borderRadius: "12px", boxShadow: "0 10px 30px rgba(0,0,0,0.05)" }}>
              <div className="config-panel-top"><div><h2 style={{ fontWeight: 800 }}>Define the world</h2><p style={{ opacity: 0.7 }}>Configure how the AI architecture learns state-transition dynamics P(S_t+1 | S_t).</p></div><span className="config-chip"><span className="status-dot" /> OFFLINE · Sequence Model</span></div>
              <div className="form-grid">
                <label className="field-label">MODEL ARCHITECTURE<select value={architecture} onChange={(event) => setArchitecture(event.target.value)} data-testid="architecture-select" style={{ background: "transparent", border: "1px solid var(--border)", padding: "12px" }}><option>Temporal Transformer</option><option>LSTM State Encoder</option><option>Graph Transition Model</option></select></label>
                <label className="field-label">EXPLAINABILITY<select value={explainability} onChange={(event) => setExplainability(event.target.value)} data-testid="explainability-select" style={{ background: "transparent", border: "1px solid var(--border)", padding: "12px" }}><option>Attention weights</option><option>SHAP Feature Attribution</option></select></label>
                <label className="field-label">FORWARD ROLLOUT<select value={horizon} onChange={(event) => setHorizon(event.target.value)} data-testid="horizon-select" style={{ background: "transparent", border: "1px solid var(--border)", padding: "12px" }}><option value="5">K = 5 steps</option><option value="8">K = 8 steps</option><option value="12">K = 12 steps</option><option value="20">K = 20 steps</option></select></label>
                <label className="field-label">STATE WINDOW<select value={windowSize} onChange={(event) => setWindowSize(event.target.value)} data-testid="window-size-select" style={{ background: "transparent", border: "1px solid var(--border)", padding: "12px" }}><option value="25">25 flows / state</option><option value="50">50 flows / state</option><option value="100">100 flows / state</option><option value="250">250 flows / state</option></select></label>
              </div>
              <div className="pipeline-row" data-testid="inference-pipeline"><span className="pipeline-step pipeline-step-active"><span>01</span> embed state S_t</span><span className="pipeline-arrow">?</span><span className="pipeline-step"><span>02</span> apply transition P(S_t+1|S_t)</span><span className="pipeline-arrow">?</span><span className="pipeline-step"><span>03</span> forward simulate</span><span className="pipeline-arrow">?</span><span className="pipeline-step"><span>04</span> explain attention</span></div>
              <Button className="run-button" disabled={!file || !inspection?.rows || runMutation.isPending} onClick={() => file && runMutation.mutate(file)} data-testid="run-inference-button" style={{ background: "#111", color: "#fff", borderRadius: "0", padding: "24px" }}><Play size={17} fill="currentColor" /> {runMutation.isPending ? "SIMULATING TRAJECTORY…" : "RUN FORWARD SIMULATION"}<ArrowRight size={17} /></Button>
              {runMutation.isError && <p className="inline-error" data-testid="inference-error">{formatError(runMutation.error)}</p>}
              <p className="config-footnote" style={{ opacity: 0.5 }}><Clock3 size={13} /> Generates timeline probability score and maps to MITRE ATT&amp;CK phases</p>
            </div>"""

content = content.replace(old_hero, new_hero)
content = content.replace(old_config, new_config)

with open("frontend/src/pages/Home.tsx", "w") as f:
    f.write(content)

print("Patched Home.tsx")
