import time
import numpy as np

class FlowAggregator:
    """
    Groups individual connections into time windows.
    Computes 17 features per window.
    """
    def __init__(self, window_seconds: int = 5):
        self.window_seconds = window_seconds
        self._buffer: list[dict] = []
        self._window_start: float = time.time()

    def add(self, conn_snapshot: dict) -> None:
        """Add a psutil connection snapshot to the buffer."""
        self._buffer.append({**conn_snapshot, "ts": time.time()})

    def flush(self) -> np.ndarray | None:
        """
        If window_seconds have elapsed, compute and return the 17-feature vector.
        Returns None if the window has not elapsed yet or buffer is empty.
        """
        now = time.time()
        if now - self._window_start < self.window_seconds:
            return None
        if not self._buffer:
            self._window_start = now
            return None
        vector = self._compute(self._buffer)
        self._buffer = []
        self._window_start = now
        return vector

    def _compute(self, events: list[dict]) -> np.ndarray:
        import pandas as pd
        from .features import extract_features
        # Create a simple dataframe from events
        
        # We need to adapt the single events into a format extract_features can use
        # For a single flow window composed of multiple packets, we aggregate them:
        
        tot_bytes = sum(e.get("packet_size", 0) or 0 for e in events)
        tot_packets = len(events)
        
        # approximate duration
        t_min = min(e["ts"] for e in events)
        t_max = max(e["ts"] for e in events)
        flow_duration_ms = max(1.0, (t_max - t_min) * 1000)
        
        # IAT
        ts_sorted = sorted([e["ts"] for e in events])
        iats = [ts_sorted[i] - ts_sorted[i-1] for i in range(1, len(ts_sorted))]
        iat_mean_ms = np.mean(iats) * 1000 if iats else 0.0
        iat_std_ms = np.std(iats) * 1000 if len(iats) > 1 else 0.0
        
        # port
        dst_ports = [e.get("destination_port", 0) or 0 for e in events]
        src_ports = [e.get("source_port", 0) or 0 for e in events]
        
        # Most common dst port
        from collections import Counter
        dst_port_most_common = Counter(dst_ports).most_common(1)[0][0] if dst_ports else 0
        src_port_most_common = Counter(src_ports).most_common(1)[0][0] if src_ports else 0
        
        # flags
        flags_list = [e.get("tcp_flags", "").upper() for e in events]
        syn = sum(1 for f in flags_list if "S" in f or "SYN" in f)
        rst = sum(1 for f in flags_list if "R" in f or "RST" in f)
        psh = sum(1 for f in flags_list if "P" in f or "PSH" in f)
        ack = sum(1 for f in flags_list if "A" in f or "ACK" in f)
        urg = sum(1 for f in flags_list if "U" in f or "URG" in f)
        fin = sum(1 for f in flags_list if "F" in f or "FIN" in f)
        
        df = pd.DataFrame([{
            "TotBytes": tot_bytes,
            "TotPkts": tot_packets,
            "TotLen Fwd Pkts": tot_bytes, # assume all fwd for simplicity
            "TotLen Bwd Pkts": 0,
            "Flow Duration": flow_duration_ms * 1000, # to match microsecond typical format if needed, but our logic handles ms. Let's provide ms.
            "Dur": flow_duration_ms / 1000.0,
            "IAT": iat_mean_ms,
            "Flow IAT Std": iat_std_ms,
            "Dport": dst_port_most_common,
            "Sport": src_port_most_common,
            "SYN Flag Cnt": syn,
            "RST Flag Cnt": rst,
            "PSH Flag Cnt": psh,
            "ACK Flag Cnt": ack,
            "URG Flag Cnt": urg,
            "FIN Flag Cnt": fin,
        }])
        
        # Adjust features logic: features.py expects flow duration in ms typically mapped from "Dur"
        X = extract_features(df)
        return X
