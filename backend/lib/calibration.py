"""Deterministic live-risk calibration for self-iteration proposals."""

MIN_EVIDENCE_EVENTS = 8
CALIBRATION_BASELINE = 0.22
CALIBRATION_GAIN = 0.55
MIN_PROPOSAL_DELTA = 0.005
MIN_MULTIPLIER = 0.75
MAX_MULTIPLIER = 1.35


def calibrate_multiplier(average_risk: float, current_multiplier: float) -> float:
    proposed = current_multiplier + (average_risk - CALIBRATION_BASELINE) * CALIBRATION_GAIN
    return round(max(MIN_MULTIPLIER, min(MAX_MULTIPLIER, proposed)), 3)


def proposal_value(average_risk: float, current_multiplier: float, force: bool = False) -> float | None:
    proposed = calibrate_multiplier(average_risk, current_multiplier)
    if abs(proposed - current_multiplier) >= MIN_PROPOSAL_DELTA:
        return proposed
    if not force:
        return None
    nudge = -0.02 if average_risk <= CALIBRATION_BASELINE else 0.02
    forced = round(max(MIN_MULTIPLIER, min(MAX_MULTIPLIER, current_multiplier + nudge)), 3)
    if abs(forced - current_multiplier) < MIN_PROPOSAL_DELTA:
        return None
    return forced
