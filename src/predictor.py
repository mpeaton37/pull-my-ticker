# src/predictor.py

from abc import ABC, abstractmethod
import pandas as pd
from typing import Tuple

class Predictor(ABC):
    """
    Abstract base class for all price predictors / filters.
    Allows easy swapping between Kalman, ARIMA, Prophet, LSTM, etc. later.
    """
    @abstractmethod
    def predict(self, data: pd.DataFrame) -> Tuple[float, float]:
        """
        Given historical data (with 'Close' column at minimum),
        return (predicted next price, associated uncertainty/variance)
        """
        pass

    @abstractmethod
    def predict_series(self, closes: pd.Series) -> Tuple[float, float]:
        """Convenience method taking only closing prices"""
        pass


# ────────────────────────────────────────────────────────────────
# Concrete implementation using the pybind11-wrapped Kalman filter
# ────────────────────────────────────────────────────────────────

import numpy as np
try:
    import kalman  # the pybind11 module (import kalman)
except ImportError:
    kalman = None
    print("Warning: kalman C++ module not found. KalmanPredictor will be disabled.")


class KalmanPredictor(Predictor):
    """
    Predictor using the C++ KalmanFilter exposed via pybind11.
    """

    def __init__(self,
                 process_noise: float = 1e-4,
                 measurement_noise: float = 1.0,
                 dt: float = 1.0):  # time step in days
        if kalman is None:
            raise ImportError("kalman pybind11 module not available")

        # Simple constant-velocity model (position + velocity)
        F = np.array([[1, dt],
                      [0,  1]], dtype=float)
        Q = np.array([[process_noise**2 / 4, process_noise**2 / 2],
                      [process_noise**2 / 2,   process_noise**2   ]])
        H = np.array([[1, 0]], dtype=float)
        R = np.array([[measurement_noise**2]], dtype=float)

        self.kf = kalman.KalmanFilter(F, Q, H, R)

        # Very uncertain initial state
        x0 = np.array([0.0, 0.0])
        P0 = np.eye(2) * 1e6
        self.kf.init(x0, P0)

    def _warm_up(self, closes: pd.Series):
        """Feed historical prices to bring filter into reasonable state"""
        prices = closes.dropna().to_numpy(dtype=float)
        for p in prices[:-1]:  # leave last one for prediction check
            self.kf.update_price(p)

    def predict(self, data: pd.DataFrame) -> Tuple[float, float]:
        if 'Close' not in data.columns:
            raise ValueError("DataFrame must have 'Close' column")
        return self.predict_series(data['Close'])

    def predict_series(self, closes: pd.Series) -> Tuple[float, float]:
        if closes.empty:
            return np.nan, np.nan

        self._warm_up(closes)
        # Last update with most recent price
        last_price = closes.iloc[-1]
        self.kf.update_price(last_price)

        # Get next predicted price + variance
        pred_price, variance = self.kf.get_prediction_and_variance()
        return float(pred_price), float(variance)