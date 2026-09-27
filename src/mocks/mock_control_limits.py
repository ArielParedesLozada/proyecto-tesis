"""Calculador de límites de control SIMULADO. **TEMPORAL / MOCK.**

Reglas del mock (documentadas para sustituirlas por el método estadístico real):

- Histórico: banda = media(hora del día) ± k·sigma(hora del día), con sigma
  calculada del propio historial (esbozo de un gráfico de control Shewhart).
- Predicción: banda dinámica por instante alrededor del valor predicho,
  con márgenes porcentuales fijos (simulan el intervalo de predicción).

Reemplazo futuro: crear una clase con la misma interfaz
(src.domain.control_limits.ControlLimitCalculator), p. ej.
StatisticalControlLimitCalculator, e implementar las fórmulas reales del
proyecto (Shewhart, EWMA, intervalos de predicción, etc.). El resto del
sistema no necesita cambios.
"""

from __future__ import annotations

from datetime import datetime

from src.domain.control_limits import ControlLimitCalculator
from src.domain.models import EnergyRecord, LimitSeries, PredictionResult
from src.domain.statistics import hourly_stats, mean


class MockControlLimitCalculator(ControlLimitCalculator):
    """Bandas de control mock con sigma por hora del día."""

    def __init__(self, k: float = 2.0, min_sigma: float = 1.2, forecast_margin_upper: float = 0.13, forecast_margin_lower: float = 0.16):
        self.k = k
        self.min_sigma = min_sigma
        self.forecast_margin_upper = forecast_margin_upper
        self.forecast_margin_lower = forecast_margin_lower

    def compute_history_limits(self, history: list[EnergyRecord]) -> LimitSeries:
        stats = hourly_stats(history)
        fallback_mu = mean([r.consumption for r in history])

        timestamps: list[datetime] = []
        upper: list[float] = []
        lower: list[float] = []
        for record in history:
            mu, sigma = stats.get(record.timestamp.hour, (fallback_mu, 0.0))
            sigma = max(sigma, self.min_sigma)
            timestamps.append(record.timestamp)
            upper.append(round(mu + self.k * sigma, 2))
            lower.append(round(max(0.0, mu - self.k * sigma), 2))
        return LimitSeries(timestamps=timestamps, upper=upper, lower=lower)

    def compute_forecast_limits(
        self,
        prediction: PredictionResult,
        history: list[EnergyRecord],
    ) -> LimitSeries:
        timestamps: list[datetime] = []
        upper: list[float] = []
        lower: list[float] = []
        for ts, value in zip(prediction.timestamps, prediction.values):
            timestamps.append(ts)
            upper.append(round(value * (1 + self.forecast_margin_upper), 2))
            lower.append(round(max(0.0, value * (1 - self.forecast_margin_lower)), 2))
        return LimitSeries(timestamps=timestamps, upper=upper, lower=lower)