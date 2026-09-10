"""Adaptive offline temporal network-state inference."""

import csv
import math
import statistics
import numpy as np
import pandas as pd
import joblib
from collections import Counter
from datetime import datetime, timezone
from io import StringIO
from typing import Any
from uuid import uuid4

from models.evaluation import BenchmarkMetrics, EvaluationRecord, FeatureAttribution, FlowAlert, StagePoint, TimelinePoint, MitrePrediction
from lib.features import extract_features, FEATURE_NAMES
from lib.explainability import compute_shap_rf, compute_attention_weights
from lib.sequence_models import load_forecaster
from lib.mitre_classifier import predict_mitre

SUSPICIOUS_TERMS = ("attack", "malicious", "botnet", "dos", "ddos", "scan", "brute", "exploit", "infiltration", "portscan", "heartbleed", "webattack", "patator")
BENIGN_TERMS = ("benign", "normal", "clean", "legitimate", "background")

# Column name aliases for source/destination IPs
_SRC_IP_COLS = ["Src IP", "src_ip", "Source IP", "source", "SrcAddr", "Sport", "src"]
_DST_IP_COLS = ["Dst IP", "dst_ip", "Destination IP", "destination", "DstAddr", "Dport", "dst"]
_SRC_PORT_COLS = ["Src Port", "source_port", "Sport", "src_port"]
_DST_PORT_COLS = ["Dst Port", "destination_port", "Dport", "dst_port"]
_PROTO_COLS = ["Protocol", "Proto", "protocol"]
_FLAG_COLS = ["TCP Flags", "Flags", "tcp_flags", "SYN Flag Cnt"]


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return round(max(low, min(high, value)), 3)


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def _severity(risk: float) -> str:
    if risk >= 0.82: return "Critical"
    if risk >= 0.62: return "High"
    if risk >= 0.38: return "Medium"
    return "Low"


def _stage_label_from_risk(risk: float) -> str:
    """
    Fallback stage label for timeline points that don't have a per-row MITRE prediction.
    Kept intentionally vague — only MITRE classifier output is authoritative for stage names.
    """
    if risk >= 0.82: return "High Anomaly"
    if risk >= 0.62: return "Elevated Risk"
    if risk >= 0.38: return "Moderate Activity"
    return "Baseline"


def _parse(raw: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    reader = csv.DictReader(StringIO(raw.decode("utf-8-sig", errors="replace")))
    headers = [header.strip() for header in (reader.fieldnames or []) if header]
    if not headers:
        raise ValueError("The CSV needs a header row.")
    rows = [{key.strip(): value for key, value in row.items() if key} for row in reader]
    rows = [row for row in rows if any(str(value).strip() for value in row.values())]
    if not rows:
        raise ValueError("The CSV has no telemetry rows to evaluate.")
    return headers, rows


def _find_col(row: dict, aliases: list[str]) -> str:
    """Return the value of the first matching column alias, or empty string."""
    for alias in aliases:
        if alias in row:
            v = str(row[alias]).strip()
            if v:
                return v
    return "—"


def _windows(risks: list[float], window_size: int) -> list[float]:
    if len(risks) <= window_size:
        return risks or [0.0]
    grouped = [statistics.fmean(risks[start:start + window_size]) for start in range(0, len(risks), window_size)]
    target = max(12, min(48, round(math.sqrt(len(grouped)) * 5)))
    if len(grouped) <= target:
        return grouped
    bucket_size = math.ceil(len(grouped) / target)
    return [statistics.fmean(grouped[start:start + bucket_size]) for start in range(0, len(grouped), bucket_size)]


def _metrics(actual: list[bool], predicted: list[bool]) -> dict[str, float]:
    tp = sum(a and p for a, p in zip(actual, predicted))
    fp = sum(not a and p for a, p in zip(actual, predicted))
    fn = sum(a and not p for a, p in zip(actual, predicted))
    tn = sum(not a and not p for a, p in zip(actual, predicted))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(0.0001, precision + recall)
    return {"f1": round(f1, 3), "precision": round(precision, 3), "recall": round(recall, 3), "false_positive_rate": round(fp / max(1, fp + tn), 3)}


def _forecast_sequence(observed: list[float], architecture: str, horizon: int) -> list[float]:
    forecaster, _ = load_forecaster(architecture, horizon)
    if forecaster is None:
        # RandomForest path: use AutoReg statistical forecast
        from statsmodels.tsa.ar_model import AutoReg
        lags = min(3, len(observed) - 1)
        # AutoReg needs at least lags+1 data points after hold_back
        min_needed = lags + lags + 1
        if lags < 1 or len(observed) < min_needed:
            # Not enough data — extrapolate from the last value with mild decay
            last = observed[-1] if observed else 0.0
            return [_clip(last * (0.95 ** i)) for i in range(horizon)]
        model = AutoReg(observed, lags=lags)
        fitted = model.fit()
        return [_clip(v) for v in fitted.forecast(horizon)]

    import torch
    seq = observed[-16:]
    if len(seq) < 16:
        seq = [0.0] * (16 - len(seq)) + seq
    x = torch.tensor(seq, dtype=torch.float32).unsqueeze(0).unsqueeze(-1)  # (1, 16, 1)
    with torch.no_grad():
        preds = forecaster(x).squeeze(0).tolist()
    return [_clip(v) for v in preds]


def _build_flows(rows: list[dict], raw_risks: list[float], headers: list[str]) -> list[FlowAlert]:
    """Build real FlowAlert records from CSV rows with actual source/destination data."""
    flows = []
    # Sort by risk descending to surface the most dangerous flows
    indexed = sorted(enumerate(raw_risks), key=lambda x: x[1], reverse=True)
    seen_ids: set[str] = set()

    for rank, (i, risk) in enumerate(indexed[:50]):
        if rank >= 50:
            break
        row = rows[i]

        src = _find_col(row, _SRC_IP_COLS)
        dst = _find_col(row, _DST_IP_COLS)
        src_port = _find_col(row, _SRC_PORT_COLS)
        dst_port = _find_col(row, _DST_PORT_COLS)
        proto = _find_col(row, _PROTO_COLS) or "TCP"
        flags = _find_col(row, _FLAG_COLS) or "—"

        # Timestamp from common column names
        ts = _find_col(row, ["Timestamp", "timestamp", "Time", "time", "Flow ID"])
        if ts == "—":
            ts = f"row-{i}"

        # Composite source/destination with port if available
        src_disp = f"{src}:{src_port}" if src_port != "—" else src
        dst_disp = f"{dst}:{dst_port}" if dst_port != "—" else dst

        flow_id = f"FLOW-{i:04d}"
        if flow_id in seen_ids:
            continue
        seen_ids.add(flow_id)

        sev = _severity(risk)
        # Stage from risk level — honest label
        stage = _stage_label_from_risk(risk)

        # Signal: describe what triggered the risk
        signal_parts = []
        syn_val = _find_col(row, ["SYN Flag Cnt", "syn_count"])
        if syn_val not in ("—", "0", ""):
            signal_parts.append("SYN flood")
        if dst_port not in ("—", "") and dst_port.isdigit() and int(dst_port) < 1024:
            signal_parts.append("privileged port")
        if not signal_parts:
            signal_parts.append("anomalous flow")
        signal = ", ".join(signal_parts)

        flows.append(FlowAlert(
            id=flow_id,
            timestamp=ts,
            source=src_disp,
            destination=dst_disp,
            protocol=proto,
            flags=flags,
            risk=_clip(risk),
            severity=sev,
            stage=stage,
            signal=signal,
        ))

    return flows


def run_world_model(raw: bytes, filename: str, architecture: str, horizon: int, window_size: int, explainability: str, context_multiplier: float = 1.0) -> EvaluationRecord:
    headers, rows = _parse(raw)
    df = pd.DataFrame(rows)
    X = extract_features(df)

    import os
    model_path = os.path.join(os.path.dirname(__file__), "..", "cic_ids_model.pkl")
    rf_pipeline = joblib.load(model_path)

    probs = rf_pipeline.predict_proba(X)[:, 1]
    raw_risks = [_clip(float(v) * context_multiplier) for v in probs]

    # Temporal smoothing with Holt-Winters EMA
    temporal = []
    if len(raw_risks) > 3:
        try:
            from statsmodels.tsa.holtwinters import SimpleExpSmoothing
            model = SimpleExpSmoothing(np.array(raw_risks), initialization_method="estimated")
            fit = model.fit(smoothing_level=0.3, optimized=False)
            temporal = [_clip(float(v)) for v in fit.fittedvalues]
        except Exception:
            temporal = raw_risks[:]
    else:
        temporal = raw_risks[:]

    row_risks = temporal
    observed = _windows(row_risks, max(1, min(500, int(window_size))))

    forecast = _forecast_sequence(observed, architecture, horizon)

    # Timeline: stage labels are honest risk-level descriptors, NOT fabricated ATT&CK stages
    timeline = [
        TimelinePoint(
            label=f"T-{len(observed) - index}",
            probability=_clip(value),
            kind="observed",
            stage=_stage_label_from_risk(value),
        )
        for index, value in enumerate(observed)
    ]
    timeline += [
        TimelinePoint(
            label=f"T+{index}",
            probability=value,
            kind="forecast",
            stage=_stage_label_from_risk(value),
        )
        for index, value in enumerate(forecast, start=1)
    ]

    risk_score = _clip(max(observed + forecast))
    forecast_probability = _clip(forecast[-1])

    # MITRE predictions — authoritative source for stage names
    # Convert from lib.mitre_classifier.MitrePrediction to plain dicts
    # so Pydantic can coerce to models.evaluation.MitrePrediction
    raw_mitre = predict_mitre(X)
    mitre_predictions = [MitrePrediction(**p.model_dump()) for p in raw_mitre]
    top_mitre = mitre_predictions[0] if mitre_predictions else None
    current_stage = top_mitre.stage if top_mitre else "Unknown"
    forecast_stage = top_mitre.stage if top_mitre else "Unknown"

    # Explainability
    shap_computed = False
    attention_weights = None
    attributions = []
    _, expl_method = load_forecaster(architecture, horizon)

    if expl_method == "feature_importance":
        shap_computed = True
        atts = compute_shap_rf(rf_pipeline, X)
        attributions = [FeatureAttribution(**a) for a in atts]
    elif expl_method == "attention_weights":
        forecaster, _ = load_forecaster(architecture, horizon)
        seq = observed[-16:]
        if len(seq) < 16:
            seq = [0.0] * (16 - len(seq)) + seq
        atts = compute_attention_weights(forecaster, seq)
        attributions = [FeatureAttribution(**a) for a in atts]
        if attributions:
            attention_weights = attributions[0].attention_weights
    else:
        # LSTM: compute gradient-based sensitivity via finite differences
        forecaster, _ = load_forecaster(architecture, horizon)
        if forecaster is not None:
            import torch
            seq = observed[-16:]
            if len(seq) < 16:
                seq = [0.0] * (16 - len(seq)) + seq
            x_base = torch.tensor(seq, dtype=torch.float32).unsqueeze(0).unsqueeze(-1)
            x_base.requires_grad_(True)
            pred = forecaster(x_base)
            pred.sum().backward()
            grads = x_base.grad.squeeze().detach().numpy()  # (16,)
            abs_grads = np.abs(grads)
            total = abs_grads.sum() or 1.0
            ranked = sorted(enumerate(abs_grads), key=lambda x: x[1], reverse=True)[:5]
            attributions = [
                FeatureAttribution(
                    feature=f"T-{15 - t_idx}",
                    value=f"Gradient: {abs_grads[t_idx]:.4f}",
                    weight=round(float(abs_grads[t_idx]) / total, 3),
                    direction="increases risk" if grads[t_idx] > 0 else "decreases risk",
                    explanation=f"LSTM sensitivity to risk state {15 - t_idx} windows ago."
                )
                for t_idx, _ in ranked
            ]
            shap_computed = True
        else:
            attributions = []

    # Benchmarking — correctly labeled
    label_header = next((h for h in headers if "label" in h.lower()), None)
    if label_header:
        actual = [not any(term in str(row.get(label_header, "")).lower() for term in BENIGN_TERMS) for row in rows]
        source = f"Ground truth from '{label_header}' column"
        labelled_rows = len(actual)
    else:
        boundary = _percentile(raw_risks, 0.75)
        actual = [risk >= boundary for risk in raw_risks]
        source = "Estimated from top-quartile risk cluster (no label column present)"
        labelled_rows = 0

    # "RF Threshold Baseline" = same RF features, fixed 0.5 threshold (no temporal smoothing)
    baseline = _metrics(actual, [risk >= 0.5 for risk in raw_risks])
    # "World Model" = temporally smoothed RF probabilities
    world = _metrics(actual, [risk >= 0.5 for risk in temporal])
    benchmark = BenchmarkMetrics(
        world_model=world,
        logistic_baseline=baseline,  # field name preserved for schema compat; UI label is fixed separately
        lift={key: round(world[key] - baseline[key], 3) for key in world},
        source=source,
        labelled_rows=labelled_rows,
    )

    # Build real flow alerts from CSV data
    flows = _build_flows(rows, raw_risks, headers)

    # Check if sequence model weights exist — for status label
    import os as _os
    base = _os.path.dirname(__file__)
    lstm_exists = _os.path.exists(_os.path.join(base, "..", f"lstm_forecaster_k{horizon}.pt"))
    tfm_exists  = _os.path.exists(_os.path.join(base, "..", f"transformer_forecaster_k{horizon}.pt"))

    if "RandomForest" in architecture:
        arch_status = "RandomForest (trained) + AR autoregressive forecast"
    elif "LSTM" in architecture:
        arch_status = f"LSTM ({'trained' if lstm_exists else 'UNTRAINED — run train_sequence.py'})"
    elif "Transformer" in architecture:
        arch_status = f"Temporal Transformer (({'trained' if tfm_exists else 'UNTRAINED — run train_sequence.py'})"
    else:
        arch_status = architecture

    model_status = f"Active | {arch_status} | SHAP={shap_computed} | MITRE={len(mitre_predictions)} classes"

    # MITRE stage tracker (show all stages chronologically)
    stages = []
    
    # Create a dictionary of probabilities from the predictions
    prob_dict = {p.class_id: p.confidence for p in mitre_predictions}
    
    # Determine the "current" stage (highest probability)
    current_class_id = 0
    if mitre_predictions:
        current_class_id = sorted(mitre_predictions, key=lambda x: x.confidence, reverse=True)[0].class_id
        
    # The chronological order of attack stages
    from lib.mitre_classifier import MITRE_CLASSES
    chronological_ids = [0, 1, 2, 3, 4, 5]
    
    for i, cid in enumerate(chronological_ids):
        stage, tech_id, tech_name = MITRE_CLASSES[cid]
        prob = prob_dict.get(cid, 0.0)
        
        if cid == current_class_id:
            status = "current"
        elif i < chronological_ids.index(current_class_id):
            status = "complete"
        else:
            status = "pending"
            
        stages.append(StagePoint(
            name=stage,
            short_name=tech_id,
            probability=prob,
            status=status,
            tactic=tech_name,
        ))

    return EvaluationRecord(
        id=str(uuid4()), filename=filename, created_at=datetime.now(timezone.utc).isoformat(),
        rows=len(rows), features=17,
        flow_features=FEATURE_NAMES, packet_features=FEATURE_NAMES, headers=headers,
        preview=[{key: str(row.get(key, "")) for key in headers[:8]} for row in rows[:5]],
        window_size=window_size, architecture=architecture, horizon=horizon, explainability=explainability,
        current_stage=current_stage,
        forecast_stage=forecast_stage,
        risk_score=risk_score, forecast_probability=forecast_probability,
        lead_windows=0.0, timeline=timeline, stages=stages,
        mitre_predictions=mitre_predictions,
        forecast_method=expl_method,
        shap_computed=shap_computed,
        attention_weights=attention_weights,
        attributions=attributions, flows=flows,
        benchmark=benchmark, context_multiplier=context_multiplier, model_status=model_status,
    )