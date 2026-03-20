import ctypes
from abc import ABC, abstractmethod
import pandas as pd
from typing import Tuple

class Predictor(ABC):
    """
    Model-agnostic abstract base class for predictors/filters.
    Allows swapping CommonFilter (C++) with more advanced models later.
    """

    @abstractmethod
    def predict(self, data: pd.DataFrame) -> Tuple[float, float]:
        """
        Predict next stock price and associated variance.
        Data is expected to be historical DataFrame from the DB.
        Returns (predicted_price, variance)
        """
        pass


class CommonFilter(Predictor):
    """
    Initial implementation wrapping the user's C++ common filter model.
    Uses ctypes to call into a compiled shared library (common_filter.so).
    Falls back to simple statistical mean/variance if C++ call fails.
    """

    def __init__(self, lib_path: str = "./common_filter.so"):
        self.lib_path = lib_path
        self.lib = None
        try:
            self.lib = ctypes.CDLL(self.lib_path)
            # Assume C++ exports a function like: double* predict(double* prices, int n) -> [price, variance]
            self.lib.predict.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_int]
            self.lib.predict.restype = ctypes.POINTER(ctypes.c_double * 2)
        except Exception as e:
            print(f"Warning: Could not load C++ library {lib_path}: {e}. Using fallback.")

    def predict(self, data: pd.DataFrame) -> Tuple[float, float]:
        if data is None or data.empty or 'Close' not in data.columns:
            raise ValueError("Invalid data for prediction")

        prices = data['Close'].values.astype(float)

        if self.lib is not None:
            try:
                # Call C++ model
                prices_ptr = prices.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
                result_ptr = self.lib.predict(prices_ptr, len(prices))
                result = result_ptr.contents
                return float(result[0]), float(result[1])
            except Exception as e:
                print(f"C++ call failed: {e}. Falling back to statistics.")

        # Fallback statistical prediction (mean as price, variance of returns)
        predicted_price = float(prices.mean())
        if len(prices) > 1:
            variance = float(prices.var(ddof=0))
        else:
            variance = 0.0
        return predicted_price, variance
