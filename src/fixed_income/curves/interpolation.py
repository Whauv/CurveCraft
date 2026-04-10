"""Interpolation models for discount curves."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from scipy.interpolate import CubicSpline


class BaseInterpolator(ABC):
    """Abstract base class for one-dimensional interpolation on log discount factors."""

    def __init__(self, x: np.ndarray, y: np.ndarray) -> None:
        if x.ndim != 1 or y.ndim != 1:
            raise ValueError("Interpolator inputs must be one-dimensional.")
        if len(x) != len(y):
            raise ValueError("Interpolator inputs must have the same length.")
        if len(x) < 2:
            raise ValueError("Interpolator requires at least two data points.")
        if not np.all(np.diff(x) > 0.0):
            raise ValueError("Interpolator x values must be strictly increasing.")
        self.x = x
        self.y = y

    @abstractmethod
    def interpolate(self, x_new: float | np.ndarray) -> np.ndarray:
        """Interpolate log discount factors at new maturities."""


class LinearInterpolator(BaseInterpolator):
    """Linear interpolation on log discount factors."""

    def interpolate(self, x_new: float | np.ndarray) -> np.ndarray:
        """Interpolate using piecewise-linear segments."""
        values = np.asarray(x_new, dtype=float)
        return np.interp(values, self.x, self.y)


class LogLinearInterpolator(LinearInterpolator):
    """Alias for linear interpolation when inputs are log discount factors."""


class CubicSplineInterpolator(BaseInterpolator):
    """Natural cubic spline interpolation on log discount factors."""

    def __init__(self, x: np.ndarray, y: np.ndarray) -> None:
        super().__init__(x=x, y=y)
        self._spline = CubicSpline(x, y, bc_type="natural", extrapolate=True)

    def interpolate(self, x_new: float | np.ndarray) -> np.ndarray:
        """Interpolate using a natural cubic spline."""
        values = np.asarray(x_new, dtype=float)
        return np.asarray(self._spline(values), dtype=float)

