"""
ml/predictor.py
---------------
Thin inference wrapper around the trained XGBoost correlation model.

Usage
-----
    from ml.predictor import XGBPredictor
    predictor = XGBPredictor()                     # loads model once
    prob = predictor.predict_proba(alert_a, alert_b)  # 0.0 – 1.0
"""

from __future__ import annotations

import os
from typing import Any

import xgboost as xgb

from ml.features import build_pair_features
from config import DEBUG_FEATURES

# ─────────────────────────────────────────────────────────────
# Default model path — lives next to this file in ml/models/
# ─────────────────────────────────────────────────────────────
_DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "models", "xgb_correlation_model.json"
)


class XGBPredictor:
    """
    Loads the saved XGBoost model and exposes a single
    ``predict_proba`` method that returns the merge probability
    for an alert pair.

    The instance is intentionally lightweight — load it once at
    startup and reuse across all calls.
    """

    def __init__(self, model_path: str = _DEFAULT_MODEL_PATH) -> None:
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"XGBoost model not found at '{model_path}'.\n"
                "Run  python train.py  from the project root to train it first."
            )
        self._model = xgb.XGBClassifier()
        self._model.load_model(model_path)
        print(f"[XGBPredictor] Model loaded from: {model_path}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict_proba(self, alert_a: Any, alert_b: Any) -> float:
        """
        Return the probability (0.0 – 1.0) that *alert_b* should be
        merged into the same incident as *alert_a*.

        Parameters
        ----------
        alert_a, alert_b : dict or ORM row
            Each alert must expose:
                created_at, area, source_id, event_type, severity, confidence

        Returns
        -------
        float — merge probability in [0, 1]
        """
        from ml.features import FEATURE_NAMES
        features = build_pair_features(alert_a, alert_b)  # list[float], len=13
        import numpy as np

        if DEBUG_FEATURES:
            print("[FEATURES]", " | ".join(f"{n}={v:.4f}" for n, v in zip(FEATURE_NAMES, features)))
            print(f"[GEO INPUT] A=({alert_a.get('geo_lat')},{alert_a.get('geo_lng')}) "
                  f"B=({alert_b.get('geo_lat')},{alert_b.get('geo_lng')})")

        X = np.array([features], dtype=float)
        prob: float = float(self._model.predict_proba(X)[0][1])
        return prob


    def predict(self, alert_a: Any, alert_b: Any, threshold: float = 0.5) -> bool:
        """
        Binary merge decision using the given probability threshold.

        Returns True if the model predicts the alerts should be merged.
        """
        return self.predict_proba(alert_a, alert_b) >= threshold


# ─────────────────────────────────────────────────────────────
# Module-level singleton — imported by agent.py
# ─────────────────────────────────────────────────────────────
_predictor_instance: XGBPredictor | None = None


def get_predictor() -> XGBPredictor:
    """
    Return the shared module-level predictor, loading the model
    on first call (lazy singleton pattern).
    """
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = XGBPredictor()
    return _predictor_instance
