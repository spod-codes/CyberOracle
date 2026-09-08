import sys, os, numpy as np, pandas as pd, joblib, torch
sys.path.insert(0, '.')

# 1. Base RF model
clf_pipe = joblib.load('cic_ids_model.pkl')
rf = clf_pipe.named_steps['clf']
print('--- BASE RF MODEL ---')
print('  n_estimators:', rf.n_estimators)
print('  n_features_in:', rf.n_features_in_)
print('  classes:', rf.classes_.tolist())
print('  training samples (root):', rf.estimators_[0].tree_.n_node_samples[0])

# 2. MITRE classifier
mitre_pipe = joblib.load('mitre_classifier.pkl')
mitre_rf = mitre_pipe.named_steps['clf']
print()
print('--- MITRE CLASSIFIER ---')
print('  classes (MITRE IDs):', mitre_rf.classes_.tolist())
print('  n_estimators:', mitre_rf.n_estimators)
print('  training samples (root):', mitre_rf.estimators_[0].tree_.n_node_samples[0])

# 3. Sequence model weights
from lib.sequence_models import load_forecaster
print()
print('--- SEQUENCE MODEL WEIGHT SANITY ---')
for arch, label in [('LSTM State Encoder', 'LSTM'), ('Temporal Transformer', 'Transformer')]:
    for k in [5, 8, 12, 20]:
        model, method = load_forecaster(arch, k)
        params = sum(p.numel() for p in model.parameters())
        first_w = next(model.parameters())
        std = first_w.std().item()
        seq_ones = torch.ones(1, 16, 1) * 0.8   # simulate sustained high risk
        seq_zero = torch.zeros(1, 16, 1)          # baseline quiet
        with torch.no_grad():
            out_high = model(seq_ones).squeeze(0).tolist()
            out_low  = model(seq_zero).squeeze(0).tolist()
        # A trained model should predict differently for different inputs
        diff = abs(sum(out_high) - sum(out_low)) / k
        status = "OK" if diff > 0.05 else "SUSPICIOUS (may be untrained)"
        print("  " + label + " K=" + str(k) + ": params=" + str(params) + "  weight_std=" + str(round(std, 4)) + "  high_vs_low_diff=" + str(round(diff, 4)) + "  " + status)

# 4. SHAP values with contrasting inputs
from lib.features import extract_features
from lib.explainability import compute_shap_rf
df = pd.DataFrame([
    {'TotBytes': 88000000, 'TotPkts': 9200, 'Dur': 500, 'IAT': 0.05, 'Dport': 80, 'Sport': 4444, 'SYN Flag Cnt': 100, 'RST Flag Cnt': 0, 'PSH Flag Cnt': 0, 'ACK Flag Cnt': 0, 'URG Flag Cnt': 0, 'FIN Flag Cnt': 0},
    {'TotBytes': 100, 'TotPkts': 2, 'Dur': 10000, 'IAT': 5000, 'Dport': 443, 'Sport': 54321, 'SYN Flag Cnt': 0, 'RST Flag Cnt': 0, 'PSH Flag Cnt': 1, 'ACK Flag Cnt': 1, 'URG Flag Cnt': 0, 'FIN Flag Cnt': 1},
])
X = extract_features(df)
prob_ddos = clf_pipe.predict_proba(X[0:1])[0, 1]
prob_norm = clf_pipe.predict_proba(X[1:2])[0, 1]
print()
print('--- RF SCORING (contrasting inputs) ---')
print('  DDoS row prob:', round(prob_ddos, 4))
print('  Normal row prob:', round(prob_norm, 4))

shap_atts = compute_shap_rf(clf_pipe, X)
print()
print('--- SHAP ATTRIBUTIONS ---')
for a in shap_atts:
    print('  ' + a['feature'].ljust(22) + ' weight=' + str(a['weight']) + '  dir=' + a['direction'])

# 5. MITRE differentiates by traffic type
from lib.mitre_classifier import predict_mitre
preds_ddos = predict_mitre(X[0:1])
preds_norm = predict_mitre(X[1:2])
print()
print('--- MITRE CLASSIFICATION ---')
print('  DDoS input:')
for p in preds_ddos:
    print('    #' + str(p.rank) + ' ' + p.stage.ljust(22) + ' ' + p.technique_id + '  conf=' + str(p.confidence))
print('  Normal input:')
for p in preds_norm:
    print('    #' + str(p.rank) + ' ' + p.stage.ljust(22) + ' ' + p.technique_id + '  conf=' + str(p.confidence))

# 6. FlowAlert: check real IP extraction
from lib.world_model import _build_flows
rows = [
    {'Src IP': '203.0.113.55', 'Src Port': '4444', 'Dst IP': '10.0.0.1', 'Dst Port': '80', 'Protocol': 'UDP', 'TCP Flags': '', 'Timestamp': '09:00:00'},
    {'Src IP': '198.51.100.7', 'Src Port': '5555', 'Dst IP': '10.0.0.1', 'Dst Port': '80', 'Protocol': 'UDP', 'TCP Flags': '', 'Timestamp': '09:00:01'},
]
flows = _build_flows(rows, [0.91, 0.87], ['Src IP', 'Src Port', 'Dst IP', 'Dst Port', 'Protocol', 'TCP Flags', 'Timestamp'])
print()
print('--- FLOWALERT IP EXTRACTION ---')
for f in flows:
    print('  ' + f.id + '  src=' + f.source + '  dst=' + f.destination + '  risk=' + str(f.risk) + '  stage=' + f.stage)

# 7. Timeline stage labels (no ATT&CK names)
from lib.world_model import _stage_label_from_risk
labels = {r: _stage_label_from_risk(r) for r in [0.9, 0.7, 0.5, 0.2]}
print()
print('--- TIMELINE STAGE LABELS ---')
for risk, label in labels.items():
    invalid = any(x in label for x in ['Exfiltration', 'Command', 'Lateral', 'Initial', 'Reconnaissance'])
    print('  risk=' + str(risk) + ' -> "' + label + '"  ' + ('BAD - uses ATT&CK name!' if invalid else 'OK'))

print()
print('=' * 55)
print('AUDIT COMPLETE')
print('=' * 55)
