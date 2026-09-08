import sys, os
sys.path.insert(0, '.')

import pandas as pd, numpy as np

# Test 1: feature extraction
from lib.features import extract_features, FEATURE_NAMES
df = pd.DataFrame([{
    'TotBytes': 50000, 'TotPkts': 100, 'Dur': 1000, 'IAT': 10,
    'Dport': 80, 'Sport': 54321,
    'SYN Flag Cnt': 5, 'RST Flag Cnt': 0, 'PSH Flag Cnt': 0,
    'ACK Flag Cnt': 95, 'URG Flag Cnt': 0, 'FIN Flag Cnt': 0
}])
X = extract_features(df)
assert X.shape == (1, 17), "Feature shape wrong: " + str(X.shape)
print("PASS feature extraction:", X.shape)

# Test 2: RF model
import joblib
pipeline = joblib.load('cic_ids_model.pkl')
prob = pipeline.predict_proba(X)[0, 1]
print("PASS RF scoring: prob=" + str(round(prob, 3)))

# Test 3: SHAP
from lib.explainability import compute_shap_rf
atts = compute_shap_rf(pipeline, X)
assert len(atts) > 0
print("PASS SHAP: " + str(len(atts)) + " attributions, top=" + atts[0]["feature"])

# Test 4: MITRE
from lib.mitre_classifier import predict_mitre
preds = predict_mitre(X)
assert len(preds) > 0
print("PASS MITRE: top=" + preds[0].stage + " (" + str(preds[0].confidence) + ")")

# Test 5: LSTM forecaster with real weights
import torch
from lib.sequence_models import load_forecaster
model, method = load_forecaster('LSTM State Encoder', 8)
assert model is not None, "LSTM model not loaded"
seq = torch.zeros(1, 16, 1)
with torch.no_grad():
    out = model(seq)
assert out.shape == (1, 8), "LSTM output shape wrong: " + str(out.shape)
print("PASS LSTM K=8: output=" + str(tuple(out.shape)) + " method=" + method)

# Test 6: Transformer + attention weights
model_t, method_t = load_forecaster('Temporal Transformer', 8)
assert model_t is not None, "Transformer model not loaded"
with torch.no_grad():
    out_t = model_t(seq)
assert out_t.shape == (1, 8)
attn = model_t.get_attention_weights(seq)
print("PASS Transformer K=8: output=" + str(tuple(out_t.shape)) + " attn=" + str(tuple(attn.shape)))

# Test 7: RF path returns None (uses AR fallback)
model_rf, method_rf = load_forecaster('RandomForest', 8)
assert model_rf is None and method_rf == 'feature_importance'
print("PASS RF path: None model, SHAP method confirmed")

# Test 8: world_model full pipeline
from lib.world_model import run_world_model
csv_bytes = b"""Src IP,Src Port,Dst IP,Dst Port,Protocol,Flow Duration,Total Fwd Packets,Total Length of Fwd Packets,Flow IAT Mean,TTL Mean,TCP Flags,Label
203.0.113.55,4444,10.0.8.20,80,UDP,500,9200,88000000,0.05,48,,DDoS
198.51.100.7,5555,10.0.8.20,80,UDP,500,8800,84000000,0.04,47,,DDoS
185.220.101.3,6666,10.0.8.20,80,UDP,500,9400,90000000,0.03,46,,DDoS
203.0.113.88,7777,10.0.8.20,80,UDP,500,9100,87500000,0.04,48,,DDoS
"""
rec = run_world_model(csv_bytes, "smoke_test.csv", "RandomForest", 8, 50, "SHAP Feature Attribution")
assert rec.risk_score >= 0 and rec.risk_score <= 1
assert len(rec.timeline) > 0
assert len(rec.flows) > 0
assert rec.flows[0].source != "src", "FlowAlert still using placeholder source"
assert rec.flows[0].source != "—", "FlowAlert has no source IP"
print("PASS world_model pipeline: risk=" + str(rec.risk_score) + " flows=" + str(len(rec.flows)) + " top_flow_src=" + rec.flows[0].source)

print()
print("=" * 50)
print("ALL 8 SMOKE TESTS PASSED")
print("=" * 50)
