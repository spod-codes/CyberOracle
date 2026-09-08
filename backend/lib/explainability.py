import numpy as np
import shap
from .features import FEATURE_NAMES

def _shap_explanation(feature_name: str) -> str:
    explanations = {
        "tot_bytes": "Total payload volume implies data movement or exfiltration.",
        "tot_packets": "High packet counts often denote flooding or sustained connection.",
        "fwd_bwd_ratio": "Asymmetric data flow is common in C2 and exfiltration.",
        "flow_duration_ms": "Long-lived flows can indicate persistence; short flows indicate scanning.",
        "iat_std_ms": "Burstiness (high variance) mimics beaconing or automated tasks.",
        "pps": "High packets-per-second is a strong indicator of volumetric attacks.",
        "dst_port_freq": "High frequency of a single destination port implies targeted service scanning.",
        "flag_syn": "Excessive SYN flags suggest connection exhaustion (SYN flooding) or scanning.",
        "flag_rst": "High RST counts suggest evasive behaviour or forced resets.",
        "dst_port_privileged": "Targeting privileged ports (<=1024) indicates lateral movement or exploitation.",
    }
    return explanations.get(feature_name, f"The {feature_name} metric deviates from benign baselines.")

def compute_shap_rf(pipeline, X: np.ndarray) -> list[dict]:
    """
    Compute SHAP values for the RF classifier in the pipeline.
    Returns top-5 features by absolute mean SHAP value.
    """
    clf = pipeline.named_steps["clf"]
    scaler = pipeline.named_steps["scaler"]
    X_scaled = scaler.transform(X)
    
    # Take a subsample for speed if X is too large
    if len(X_scaled) > 500:
        idx = np.random.choice(len(X_scaled), 500, replace=False)
        X_scaled = X_scaled[idx]

    explainer = shap.TreeExplainer(clf)
    
    try:
        shap_values = explainer.shap_values(X_scaled)
        
        if isinstance(shap_values, list):
            # scikit-learn random forest returns list [class0, class1]
            attack_shap = shap_values[1]
        else:
            # binary sometimes just returns (n, features)
            if len(shap_values.shape) == 3:
                attack_shap = shap_values[:, :, 1]
            else:
                attack_shap = shap_values

        mean_abs = np.abs(attack_shap).mean(axis=0)  # (n_features,)
        total = mean_abs.sum() or 1.0
        
        ranked = sorted(zip(mean_abs, FEATURE_NAMES), key=lambda x: x[0], reverse=True)[:5]
        
        results = []
        for weight, name in ranked:
            w_norm = round(float(weight) / total, 3)
            # Find the mean directional impact of this feature
            idx = FEATURE_NAMES.index(name)
            direction_mean = attack_shap[:, idx].mean()
            
            results.append({
                "feature": name,
                "value": f"SHAP: {w_norm:.4f}",
                "weight": w_norm,
                "direction": "increases risk" if direction_mean > 0 else "decreases risk",
                "explanation": _shap_explanation(name),
            })
        return results
    except Exception as e:
        print("SHAP error:", e)
        return []

def compute_attention_weights(model, X_seq: np.ndarray) -> list[dict]:
    """
    Extract attention weights from the Temporal Transformer model.
    """
    import torch
    x = torch.tensor(X_seq, dtype=torch.float32).unsqueeze(0).unsqueeze(-1)
    
    try:
        attn = model.get_attention_weights(x)
        # attn: (num_layers, batch, nhead, seq_len, seq_len)
        # Average across layers and heads
        # Shape: (1, 16, 16)
        mean_attn = attn.mean(dim=0).mean(dim=1).squeeze(0) # (16, 16)
        
        # We want the attention weights that the *last* token (current time) pays to previous tokens
        last_token_attn = mean_attn[-1].detach().numpy() # (16,)
        
        results = []
        total = np.sum(last_token_attn) or 1.0
        
        ranked = sorted(enumerate(last_token_attn), key=lambda x: x[1], reverse=True)[:5]
        for t_idx, weight in ranked:
            w_norm = round(float(weight) / total, 3)
            results.append({
                "feature": f"T-{15 - t_idx}",
                "value": f"Attention: {w_norm:.3f}",
                "weight": w_norm,
                "direction": "historical context",
                "explanation": f"The model heavily attended to the state {15 - t_idx} windows ago to predict the next trajectory.",
                "attention_weights": last_token_attn.tolist()
            })
            
        return results
    except Exception as e:
        print("Attention error:", e)
        return []
