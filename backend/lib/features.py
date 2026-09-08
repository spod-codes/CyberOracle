import numpy as np
import pandas as pd

FEATURE_NAMES = [
    # Volumetric
    "tot_bytes",          # total bytes in window (fwd + bwd)
    "tot_packets",        # total packets in window
    "bytes_per_packet",   # tot_bytes / max(1, tot_packets)
    "fwd_bwd_ratio",      # fwd_bytes / max(1, bwd_bytes)

    # Timing
    "flow_duration_ms",   # duration of the flow window in milliseconds
    "iat_mean_ms",        # mean inter-arrival time between packets
    "iat_std_ms",         # std deviation of inter-arrival time (variance = burstiness)
    "pps",                # packets per second = tot_packets / max(0.001, duration_s)

    # Port behaviour
    "dst_port_privileged",  # 1.0 if dst_port < 1024, else 0.0
    "dst_port_freq",        # relative frequency of this dst_port in the window
    "src_port_ephemeral",   # 1.0 if src_port >= 49152, else 0.0

    # TCP flags
    "flag_syn",       # count of SYN flags in window
    "flag_rst",       # count of RST flags in window
    "flag_psh",       # count of PSH flags in window
    "flag_ack",       # count of ACK flags in window
    "flag_urg",       # count of URG flags in window
    "flag_fin",       # count of FIN flags in window
]

FEATURE_DIM = 17

COLUMN_MAP = {
    "tot_bytes":       ["TotBytes", "TotLen Fwd Pkts", "total_bytes", "bytes"],
    "tot_packets":     ["TotPkts", "Tot Fwd Pkts", "total_packets", "packets"],
    "flow_duration_ms":["Dur", "Flow Duration", "duration"],
    "iat_mean_ms":     ["IAT", "Flow IAT Mean", "iat_mean"],
    "iat_std_ms":      ["Flow IAT Std", "iat_std"],
    "dst_port":        ["Dport", "Dst Port", "destination_port", "Destination Port"],
    "src_port":        ["Sport", "Src Port", "source_port", "Source Port"],
    "flag_syn":        ["SYN Flag Cnt", "syn_count", "SYN Flag Count"],
    "flag_rst":        ["RST Flag Cnt", "rst_count", "RST Flag Count"],
    "flag_psh":        ["PSH Flag Cnt", "psh_count", "PSH Flag Count"],
    "flag_ack":        ["ACK Flag Cnt", "ack_count", "ACK Flag Count"],
    "flag_urg":        ["URG Flag Cnt", "urg_count", "URG Flag Count"],
    "flag_fin":        ["FIN Flag Cnt", "fin_count", "FIN Flag Count"],
    "bwd_bytes":       ["TotLen Bwd Pkts", "bwd_bytes"],
    "fwd_bytes":       ["TotLen Fwd Pkts", "fwd_bytes"],
}

def extract_features(df: pd.DataFrame) -> np.ndarray:
    """
    Given a pandas dataframe (e.g. from a CSV), extract the 17-dimensional
    feature vector array.
    """
    df_cols = df.columns.str.strip()
    
    # Helper to find column by fuzzy match
    def get_col(fuzzy_names):
        for name in fuzzy_names:
            if name in df_cols:
                return pd.to_numeric(df[name], errors='coerce').fillna(0.0).values
        return np.zeros(len(df))

    tot_bytes = get_col(COLUMN_MAP["tot_bytes"])
    bwd_bytes = get_col(COLUMN_MAP["bwd_bytes"])
    # If tot_bytes is just fwd_bytes in CIC-IDS, we need to add bwd_bytes
    if "TotLen Fwd Pkts" in df_cols and "TotLen Bwd Pkts" in df_cols:
        tot_bytes = get_col(["TotLen Fwd Pkts"]) + get_col(["TotLen Bwd Pkts"])
    
    tot_packets = get_col(COLUMN_MAP["tot_packets"])
    if "Tot Fwd Pkts" in df_cols and "Tot Bwd Pkts" in df_cols:
        tot_packets = get_col(["Tot Fwd Pkts"]) + get_col(["Tot Bwd Pkts"])
        
    fwd_bytes = get_col(COLUMN_MAP["fwd_bytes"])
    if np.sum(fwd_bytes) == 0:
        fwd_bytes = tot_bytes - bwd_bytes

    flow_duration = get_col(COLUMN_MAP["flow_duration_ms"])
    iat_mean = get_col(COLUMN_MAP["iat_mean_ms"])
    iat_std = get_col(COLUMN_MAP["iat_std_ms"])

    dst_port = get_col(COLUMN_MAP["dst_port"])
    src_port = get_col(COLUMN_MAP["src_port"])

    syn = get_col(COLUMN_MAP["flag_syn"])
    rst = get_col(COLUMN_MAP["flag_rst"])
    psh = get_col(COLUMN_MAP["flag_psh"])
    ack = get_col(COLUMN_MAP["flag_ack"])
    urg = get_col(COLUMN_MAP["flag_urg"])
    fin = get_col(COLUMN_MAP["flag_fin"])
    
    # If CTU-13 state is present, parse flags
    if "State" in df_cols:
        state_str = df["State"].astype(str).str.upper()
        syn = state_str.str.count('S').values
        rst = state_str.str.count('R').values
        psh = state_str.str.count('P').values
        ack = state_str.str.count('A').values
        urg = state_str.str.count('U').values
        fin = state_str.str.count('F').values

    # Construct the 17 features
    X = np.zeros((len(df), FEATURE_DIM), dtype=np.float64)
    
    X[:, 0] = tot_bytes
    X[:, 1] = tot_packets
    X[:, 2] = tot_bytes / np.maximum(1, tot_packets)
    X[:, 3] = fwd_bytes / np.maximum(1, bwd_bytes)
    
    X[:, 4] = flow_duration
    X[:, 5] = iat_mean
    X[:, 6] = iat_std
    # pps
    X[:, 7] = tot_packets / np.maximum(0.001, flow_duration / 1000000.0)
    
    X[:, 8] = (dst_port < 1024).astype(float)
    port_counts = pd.Series(dst_port).value_counts(normalize=True)
    X[:, 9] = pd.Series(dst_port).map(port_counts).fillna(0).values
    X[:, 10] = (src_port >= 49152).astype(float)
    
    X[:, 11] = syn
    X[:, 12] = rst
    X[:, 13] = psh
    X[:, 14] = ack
    X[:, 15] = urg
    X[:, 16] = fin

    # Handle NaNs and Infs
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    return X
