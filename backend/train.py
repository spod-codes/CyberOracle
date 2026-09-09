import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import joblib
import os
import glob
import sys

from lib.features import extract_features

def get_mitre_label(label_str: str) -> int:
    """
    Map CIC-IDS-2018 / CTU-13 label strings to MITRE ATT&CK class IDs:
      0 = Reconnaissance     (T1046)
      1 = Initial Access      (T1133)
      2 = Lateral Movement    (T1021)
      3 = Command & Control   (T1071)
      4 = Exfiltration        (T1048)
      5 = Denial of Service   (T1498)
    """
    s = str(label_str).lower()

    # DoS / DDoS → class 5
    if any(x in s for x in ("ddos", "dos-", "dos ", "hulk", "goldeneye", "slowhttptest", "slowloris", "heartbleed", "udp flood", "syn flood", "tcp flood")):
        return 5

    # Reconnaissance / scanning → class 0
    if any(x in s for x in ("portscan", "port scan", "reconnaissance", "recon", "scan")):
        return 0

    # Web-based initial access → class 1
    if any(x in s for x in ("web attack", "webattack", "brute force", "xss", "sql injection", "patator", "ftp-patator", "ssh-patator")):
        return 1

    # Lateral movement via remote services → class 2
    if any(x in s for x in ("infiltration", "lateral", "smb", "rce", "pass-the-hash", "pass-the-ticket")):
        return 2

    # Botnet C2 → class 3
    if any(x in s for x in ("botnet", "c2", "command", "beacon", "bot ")):
        return 3

    # Exfiltration → class 4
    if any(x in s for x in ("exfil", "data exfil", "dns tunnel", "icmp tunnel", "covert", "exfiltration")):
        return 4

    return -1  # Benign or unknown

def generate_sequence_data(X_all, y_pred_prob, out_dir):
    print("Generating sequence training data...")
    # Simulate windowing by grouping every 50 rows
    window_size = 50
    num_windows = len(y_pred_prob) // window_size
    
    if num_windows < 50:
        print("Not enough data to generate sequences.")
        return

    window_risks = []
    for i in range(num_windows):
        window_risks.append(np.mean(y_pred_prob[i*window_size : (i+1)*window_size]))
    
    seq_len = 16
    horizons = [5, 8, 12, 20]
    
    X_seq = []
    Y_seq = {k: [] for k in horizons}
    
    for i in range(len(window_risks) - seq_len - max(horizons)):
        x_s = window_risks[i : i+seq_len]
        X_seq.append(x_s)
        for k in horizons:
            Y_seq[k].append(window_risks[i+seq_len : i+seq_len+k])
            
    X_seq_np = np.array(X_seq)
    for k in horizons:
        y_seq_np = np.array(Y_seq[k])
        out_path = os.path.join(out_dir, f"sequence_training_data_k{k}.npz")
        np.savez(out_path, X=X_seq_np, y=y_seq_np)
    print("Saved sequence data to", out_dir)

def train():
    print("Loading all user-provided datasets...")
    X_list = []
    y_bin_list = []
    y_mitre_list = []
    
    # --- 1. Load CIC-IDS-2018 ---
    cic_path = os.path.join(os.path.dirname(__file__), "datasets", "cic-ids2018", "sample_cic2018.csv")
    if os.path.exists(cic_path):
        print(f"Parsing {cic_path}")
        df_cic = pd.read_csv(cic_path)
        
        X_cic = extract_features(df_cic)
        
        labels = df_cic['Label'].astype(str).str.lower()
        y_bin = np.where(labels.str.contains('benign'), 0, 1)
        y_mitre = np.array([get_mitre_label(l) for l in labels])
        
        X_list.append(X_cic)
        y_bin_list.append(y_bin)
        y_mitre_list.append(y_mitre)
        print(f"  -> Extracted {len(X_cic)} vectors from CIC-IDS-2018")
    
    # --- 2. Load CTU-13 ---
    ctu_base_dir = os.path.join(os.path.dirname(__file__), "datasets", "ctu-13")
    ctu_files = glob.glob(os.path.join(ctu_base_dir, "**", "*.binetflow"), recursive=True)
    
    print(f"Found {len(ctu_files)} CTU-13 dataset files.")
    
    for f in ctu_files:
        print(f"Parsing {f} (sampling 15,000 rows)...")
        try:
            df_ctu = pd.read_csv(f, nrows=15000)
            X_ctu = extract_features(df_ctu)
            
            labels = df_ctu['Label'].astype(str).str.lower()
            y_bin = np.where(labels.str.contains('normal|background'), 0, 1)
            y_mitre = np.array([get_mitre_label(l) for l in labels])
            
            X_list.append(X_ctu)
            y_bin_list.append(y_bin)
            y_mitre_list.append(y_mitre)
            print(f"  -> Extracted {len(X_ctu)} vectors")
        except Exception as e:
            print(f"  -> Error parsing {f}: {e}")
    
    if not X_list:
        print("No datasets found. Cannot train.")
        return

    # --- 3. Merge Datasets ---
    X = np.vstack(X_list)
    y_bin = np.concatenate(y_bin_list)
    y_mitre = np.concatenate(y_mitre_list)
    
    print(f"Total Unified Training Set: {X.shape[0]:,} vectors with {X.shape[1]} dimensions.")
    
    # Split
    X_train, X_test, y_train_bin, y_test_bin, y_train_mitre, y_test_mitre = train_test_split(
        X, y_bin, y_mitre, test_size=0.2, random_state=42, stratify=y_bin
    )
    
    out_dir = os.path.dirname(__file__)

    # --- 4. Train Base RF Model ---
    print("Fitting Supervised RandomForestClassifier on real data...")
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", RandomForestClassifier(n_estimators=200, max_depth=None, random_state=42, n_jobs=-1))
    ])
    pipeline.fit(X_train, y_train_bin)
    
    model_path = os.path.join(out_dir, "cic_ids_model.pkl")
    joblib.dump(pipeline, model_path)
    print(f"Unified model successfully saved to {model_path}!")
    
    # Eval Base Model
    y_pred_bin = pipeline.predict(X_test)
    print("\n" + "="*60)
    print("BASE RF MODEL EVALUATION")
    print("="*60)
    print(classification_report(y_test_bin, y_pred_bin, target_names=["Benign", "Attack"]))
    
    # --- 5. Train MITRE Classifier ---
    print("\nFitting MITRE Classifier...")
    # Filter out benign traffic (-1) for MITRE classifier
    mask_train = y_train_mitre != -1
    mask_test = y_test_mitre != -1
    
    if np.sum(mask_train) > 0:
        mitre_pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", RandomForestClassifier(n_estimators=100, max_depth=None, random_state=42, n_jobs=-1))
        ])
        mitre_pipeline.fit(X_train[mask_train], y_train_mitre[mask_train])
        
        mitre_path = os.path.join(out_dir, "mitre_classifier.pkl")
        joblib.dump(mitre_pipeline, mitre_path)
        print(f"MITRE classifier saved to {mitre_path}!")
        
        y_pred_mitre = mitre_pipeline.predict(X_test[mask_test])
        print("\nMITRE CLASSIFIER EVALUATION")
        print("Macro F1:", f1_score(y_test_mitre[mask_test], y_pred_mitre, average='macro'))
        print(classification_report(y_test_mitre[mask_test], y_pred_mitre))
    else:
        print("No MITRE labelled attack data found. Skipping MITRE training.")
        
    # --- 6. Generate Sequence Training Data ---
    # We use the full X to generate the sequential risk predictions
    y_pred_prob = pipeline.predict_proba(X)[:, 1]
    
    data_dir = os.path.join(out_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    generate_sequence_data(X, y_pred_prob, data_dir)
    
if __name__ == "__main__":
    train()
