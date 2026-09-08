import os
import torch
from .lstm_forecaster import LSTMForecaster
from .transformer_forecaster import TemporalTransformerForecaster

def load_forecaster(architecture: str, horizon: int) -> tuple[object, str]:
    """
    Returns (model, explainability_method) for the given architecture.
    
    architecture must be one of:
      "RandomForest"             → use EMA smoothing (no sequence model)
      "LSTM State Encoder"       → use LSTMForecaster
      "Temporal Transformer"     → use TemporalTransformerForecaster
    """
    base_dir = os.path.join(os.path.dirname(__file__), "..", "..")
    
    if "RandomForest" in architecture:
        return None, "feature_importance"  # RF uses SHAP TreeExplainer
        
    elif "LSTM" in architecture:
        model = LSTMForecaster(horizon=horizon)
        path = os.path.join(base_dir, f"lstm_forecaster_k{horizon}.pt")
        if os.path.exists(path):
            model.load_state_dict(torch.load(path, map_location="cpu"))
        else:
            print(f"Warning: LSTM model {path} not found. Using untrained fallback.")
        model.eval()
        return model, "gradient"
        
    elif "Transformer" in architecture:
        model = TemporalTransformerForecaster(horizon=horizon)
        path = os.path.join(base_dir, f"transformer_forecaster_k{horizon}.pt")
        if os.path.exists(path):
            model.load_state_dict(torch.load(path, map_location="cpu"))
        else:
            print(f"Warning: Transformer model {path} not found. Using untrained fallback.")
        model.eval()
        return model, "attention_weights"
    else:
        raise ValueError(f"Unknown architecture: {architecture!r}")
