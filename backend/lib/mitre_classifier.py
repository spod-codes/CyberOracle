import os
import joblib
import numpy as np

MITRE_CLASSES = {
    0: ("Reconnaissance",       "T1046",  "Network Service Discovery"),
    1: ("Initial Access",       "T1133",  "External Remote Services"),
    2: ("Lateral Movement",     "T1021",  "Remote Services"),
    3: ("Command & Control",    "T1071",  "Application Layer Protocol"),
    4: ("Exfiltration",         "T1048",  "Exfiltration Over Alternative Protocol"),
    5: ("Denial of Service",    "T1498",  "Network Denial of Service"),
}

class MitrePrediction:
    def __init__(self, rank, class_id, stage, technique_id, technique_name, confidence):
        self.rank = rank
        self.class_id = class_id
        self.stage = stage
        self.technique_id = technique_id
        self.technique_name = technique_name
        self.confidence = confidence

    def model_dump(self):
        return {
            "rank": self.rank,
            "class_id": self.class_id,
            "stage": self.stage,
            "technique_id": self.technique_id,
            "technique_name": self.technique_name,
            "confidence": self.confidence
        }

_MITRE_PATH = os.path.join(os.path.dirname(__file__), "..", "mitre_classifier.pkl")

try:
    _mitre_pipeline = joblib.load(_MITRE_PATH)
except Exception as e:
    _mitre_pipeline = None
    print("Warning: Could not load mitre_classifier.pkl:", e)


def predict_mitre(X: np.ndarray) -> list[MitrePrediction]:
    """
    Returns top-3 MITRE technique predictions with probabilities.
    """
    if _mitre_pipeline is None:
        # Fallback if model not trained
        return [
            MitrePrediction(1, 0, "Unknown", "T0000", "Fallback", 0.0)
        ]
        
    proba = _mitre_pipeline.predict_proba(X)
    
    # Check shape to handle case where only one class was predicted during training
    # or handle mean aggregation correctly
    mean_proba = proba.mean(axis=0) if proba.ndim > 1 else proba
    
    # We need to map model output classes (which might not be 0-5 if some were missing in training)
    # to MITRE_CLASSES
    classes = _mitre_pipeline.classes_
    
    scored_classes = []
    for i, c in enumerate(classes):
        if c in MITRE_CLASSES:
            scored_classes.append((c, mean_proba[i]))
            
    ranked = sorted(scored_classes, key=lambda x: x[1], reverse=True)
    
    predictions = []
    for i, (class_id, conf) in enumerate(ranked):
        stage, tech_id, tech_name = MITRE_CLASSES[class_id]
        predictions.append(
            MitrePrediction(
                rank=i + 1,
                class_id=class_id,
                stage=stage,
                technique_id=tech_id,
                technique_name=tech_name,
                confidence=round(float(conf), 3),
            )
        )
        
    if not predictions:
        # Failsafe
        predictions.append(MitrePrediction(1, 0, "Unknown", "T0000", "Fallback", 0.0))
        
    return predictions
