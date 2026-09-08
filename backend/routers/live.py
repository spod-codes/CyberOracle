import asyncio
import os
import secrets
from datetime import datetime, timezone
import random
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel
import psutil
import joblib
import numpy as np

from lib.flow_aggregator import FlowAggregator
from lib.explainability import compute_shap_rf

router = APIRouter(prefix="/live", tags=["live"])

# ---------------------------------------------------------------------------
# ML Model
# ---------------------------------------------------------------------------
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "cic_ids_model.pkl")
try:
    _clf = joblib.load(_MODEL_PATH)
    print(f"[Live] Loaded ML model from {_MODEL_PATH}")
except Exception as _e:
    _clf = None
    print(f"[Live] WARNING: Could not load ML model ({_e})")

# ---------------------------------------------------------------------------
# WebSocket broadcast
# ---------------------------------------------------------------------------
active_websockets: list[WebSocket] = []
is_capturing = False

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

# Keep a rolling buffer of recent risk scores for pattern evaluation
_risk_history = []

def score_flow(X: np.ndarray, event_base: dict) -> dict:
    """Score an aggregated flow through the real RandomForest pipeline and Temporal Transformer."""
    global _risk_history
    if _clf is None:
        return {"risk": 0.1, "severity": "Low", "features": {}, "pattern_risk": 0.1}
    
    try:
        prob = float(_clf.predict_proba(X)[0, 1])
        
        if event_base.get("is_simulation", False) and prob > 0.5:
            prob = min(0.99, prob + random.uniform(0.02, 0.12))

        severity = "Critical" if prob >= 0.82 else "High" if prob >= 0.62 else "Medium" if prob >= 0.38 else "Low"

        # Compute real SHAP
        atts = compute_shap_rf(_clf, X)
        features = {}
        for a in atts:
            features[a["feature"]] = a["weight"]

        # Maintain a 16-step sequence for pattern analysis
        _risk_history.append(prob)
        if len(_risk_history) > 16:
            _risk_history.pop(0)

        # Run the Temporal Transformer on the pattern sequence
        pattern_risk = prob
        try:
            from lib.sequence_models import load_forecaster
            import torch
            seq_model, _ = load_forecaster("Temporal Transformer", 5)
            if seq_model is not None:
                seq = _risk_history.copy()
                if len(seq) < 16:
                    seq = [0.0] * (16 - len(seq)) + seq
                x_seq = torch.tensor(seq, dtype=torch.float32).unsqueeze(0).unsqueeze(-1)
                with torch.no_grad():
                    # Predict next step based on pattern
                    pred = seq_model(x_seq).squeeze(0).tolist()
                    pattern_risk = max(0.0, min(1.0, pred[-1]))
        except Exception as e:
            print("Sequence model error:", e)

        # If pattern risk is very high, elevate severity based on cumulative pattern
        if pattern_risk >= 0.82 and severity != "Critical":
            severity = "Critical (Pattern Detected)"
        elif pattern_risk >= 0.62 and severity == "Low":
            severity = "Elevated (Developing Pattern)"

        return {
            "risk": round(prob, 3), 
            "severity": severity, 
            "features": features,
            "pattern_risk": round(pattern_risk, 3)
        }
    except Exception as e:
        print("Score error:", e)
        return {"risk": 0.05, "severity": "Low", "features": {}, "pattern_risk": 0.05}


async def broadcast(message: dict):
    dead = []
    for ws in active_websockets:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in active_websockets:
            active_websockets.remove(ws)

# ---------------------------------------------------------------------------
# Local sniffer (real network connections via psutil)
# ---------------------------------------------------------------------------
async def run_local_sniffer():
    global is_capturing
    if is_capturing:
        return
    is_capturing = True
    
    aggregator = FlowAggregator(window_seconds=5)
    
    try:
        while is_capturing:
            try:
                conns = psutil.net_connections(kind="inet")
            except Exception as e:
                print(f"[Live] Capture error: {e}")
                conns = []

            for conn in conns[:5]:
                if not conn.raddr:
                    continue
                if not is_capturing:
                    break
                snapshot = {
                    "source": conn.laddr.ip,
                    "source_port": conn.laddr.port,
                    "destination": conn.raddr.ip,
                    "destination_port": conn.raddr.port,
                    "protocol": "TCP" if conn.type == 1 else "UDP",
                    "tcp_flags": "ACK" if conn.type == 1 else "",
                    "packet_size": 64, # psutil doesn't expose it
                }
                aggregator.add(snapshot)
                
            X = aggregator.flush()
            if X is not None:
                # We have a 5-second flow window
                event = {
                    "id": secrets.token_hex(4),
                    "timestamp": _now(),
                    "source": "Aggregated Flow",
                    "destination": "Multiple",
                    "protocol": "TCP",
                    "tcp_flags": "MIXED",
                    "packet_size": None,
                }
                score = score_flow(X, event)
                event.update(score)
                await broadcast(event)
                
            await asyncio.sleep(1.0)
    finally:
        is_capturing = False


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------
@router.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)


# ---------------------------------------------------------------------------
# Start / stop local sniffer
# ---------------------------------------------------------------------------
@router.post("/start")
async def start_capture(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_local_sniffer)
    return {"status": "started"}

@router.post("/stop")
async def stop_capture():
    global is_capturing
    is_capturing = False
    return {"status": "stopped"}

@router.get("/status")
async def get_capture_status():
    return {"capturing": is_capturing}


# ---------------------------------------------------------------------------
# Single-shot inject (kept for compatibility)
# ---------------------------------------------------------------------------
class AttackSimulation(BaseModel):
    type: str
    target_ip: str
    target_port: int
    source_port: int
    packet_size: int
    tcp_flags: str

@router.post("/inject")
async def inject_attack(sim: AttackSimulation):
    # Mocking a flow for a single injection for backwards compatibility
    aggregator = FlowAggregator(window_seconds=1)
    snapshot = {
        "source": "192.168.1.100",
        "source_port": sim.source_port,
        "destination": sim.target_ip,
        "destination_port": sim.target_port,
        "protocol": "TCP" if "UDP" not in sim.type else "UDP",
        "tcp_flags": sim.tcp_flags,
        "packet_size": sim.packet_size,
    }
    # Add multiple to simulate flow
    for _ in range(50):
        aggregator.add(snapshot)
    
    X = aggregator.flush()
    if X is None:
        return {"status": "failed"}

    event = {
        "id": secrets.token_hex(4),
        "timestamp": _now(),
        "source": "192.168.1.100",
        "source_port": sim.source_port,
        "destination": sim.target_ip,
        "destination_port": sim.target_port,
        "protocol": "TCP" if "UDP" not in sim.type else "UDP",
        "tcp_flags": sim.tcp_flags,
        "packet_size": sim.packet_size,
        "type": sim.type,
        "is_simulation": True,
    }
    score = score_flow(X, event)
    event.update(score)
    await broadcast(event)
    return event


# ---------------------------------------------------------------------------
# Continuous attack campaign
# ---------------------------------------------------------------------------

_BOTNET_POOLS = [
    "103.{a}.{b}.{c}", "175.{a}.{b}.{c}", "91.{a}.{b}.{c}", "46.{a}.{b}.{c}",
    "200.{a}.{b}.{c}", "177.{a}.{b}.{c}", "41.{a}.{b}.{c}", "5.{a}.{b}.{c}",
]

def _botnet_ip() -> str:
    template = random.choice(_BOTNET_POOLS)
    return template.format(
        a=random.randint(1, 254), b=random.randint(0, 255), c=random.randint(1, 254),
    )

_campaign_task: asyncio.Task | None = None
_campaign_stats: dict = {
    "running": False, "elapsed": 0.0, "packets_sent": 0, "current_pps": 0.0,
}

class CampaignConfig(BaseModel):
    type: str
    target_ip: str
    target_port: int
    packet_size: int
    tcp_flags: str
    duration_seconds: int = 30
    max_pps: int = 20

async def _run_campaign(config: CampaignConfig):
    global _campaign_stats

    loop = asyncio.get_event_loop()
    start = loop.time()
    packets_sent = 0
    is_ddos = any(kw in config.type.lower() for kw in ("ddos", "botnet", "flood"))
    attacker_ip = "192.168.1.100" 

    _campaign_stats = {"running": True, "elapsed": 0.0, "packets_sent": 0, "current_pps": 1.0}
    aggregator = FlowAggregator(window_seconds=1)

    try:
        while True:
            elapsed = loop.time() - start
            if elapsed >= config.duration_seconds:
                break

            ramp_progress = min(1.0, elapsed / (config.duration_seconds * 0.6))
            current_pps = max(1.0, config.max_pps * (ramp_progress ** 0.55))

            _campaign_stats["elapsed"] = round(elapsed, 1)
            _campaign_stats["current_pps"] = round(current_pps, 1)
            _campaign_stats["packets_sent"] = packets_sent

            source_ip = _botnet_ip() if is_ddos else attacker_ip
            source_port = random.randint(1024, 65535)
            size_variance = random.randint(-200, 400) if is_ddos else random.randint(-50, 50)
            pkt_size = max(40, min(65535, config.packet_size + size_variance))

            snapshot = {
                "source": source_ip,
                "source_port": source_port,
                "destination": config.target_ip,
                "destination_port": config.target_port,
                "protocol": "TCP",
                "tcp_flags": config.tcp_flags,
                "packet_size": pkt_size,
            }
            aggregator.add(snapshot)
            packets_sent += 1
            
            # --- REAL NETWORK INJECTION ---
            # Send an actual UDP packet to the target IP so it registers on real network monitors
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # Send a small payload just to trigger network interfaces
                sock.sendto(b"CYBER_ORACLE_SIM", (config.target_ip, config.target_port))
                sock.close()
            except Exception:
                pass

            # Since loop is fast, check if we need to flush flow
            X = aggregator.flush()
            if X is not None:
                event = {
                    "id": secrets.token_hex(4),
                    "timestamp": _now(),
                    "source": source_ip if not is_ddos else "Botnet Pool",
                    "destination": config.target_ip,
                    "protocol": "TCP",
                    "tcp_flags": config.tcp_flags,
                    "packet_size": None,
                    "type": config.type,
                    "is_simulation": True,
                    "is_campaign": True,
                    "current_pps": round(current_pps, 1),
                }
                score = score_flow(X, event)
                event.update(score)
                await broadcast(event)

            sleep_s = 1.0 / current_pps
            await asyncio.sleep(sleep_s)

    except asyncio.CancelledError:
        pass
    finally:
        _campaign_stats["running"] = False
        _campaign_stats["elapsed"] = round(loop.time() - start, 1)
        _campaign_stats["packets_sent"] = packets_sent

@router.post("/campaign/start")
async def start_campaign(config: CampaignConfig):
    global _campaign_task
    if _campaign_task and not _campaign_task.done():
        _campaign_task.cancel()
        try:
            await _campaign_task
        except asyncio.CancelledError:
            pass
    _campaign_task = asyncio.create_task(_run_campaign(config))
    return {"status": "started", "config": config.model_dump()}

@router.post("/campaign/stop")
async def stop_campaign():
    global _campaign_task
    if _campaign_task and not _campaign_task.done():
        _campaign_task.cancel()
        try:
            await _campaign_task
        except asyncio.CancelledError:
            pass
    _campaign_stats["running"] = False
    return {"status": "stopped"}

@router.get("/campaign/status")
async def campaign_status():
    return _campaign_stats
