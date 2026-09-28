"""Límites de control REAL (estadísticos) para la demo AEP.

Cumple `src.domain.control_limits.ControlLimitCalculator` y sustituye a
`src.mocks.mock_control_limits.MockControlLimitCalculator`, que usaba márgenes
porcentuales fijos.

Método (gráfico de control Shewhart por hora del día, que es la sustitución
que el propio mock de `src/mocks` propone en su documentación):

- **Histórico**: para cada hora `h` (separando fin de semana de día laborable)
  se estima `mu(h)` y `sigma(h)` sobre una ventana de referencia amplia y la
  banda es `mu(h) ± k·sigma(h)`, con `k = 3` por defecto.
- **Predicción**: banda de predicción alrededor del valor predicho. El ancho
  usa la desviación residual por hora que sale del backtest del modelo
  (`residual_sigma`), no la desviación de la serie: así el intervalo representa
  el error del modelo y no la variabilidad horaria del consumo.

Si no se pasan los residuales del backtest, se cae de vuelta a `sigma(h)` de la
serie, con un mínimo relativo a la media para no producir bandas degeneradas en
horas planas.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from src.domain.control_limits import ControlLimitCalculator
from src.domain.models import EnergyRecord, LimitSeries, PredictionResult
from src.domain.statistics import mean, stddev

#: Bandas de control por defecto (Shewhart).
DEFAULT_K = 3.0
#: Ancho del intervalo de predicción, en desviaciones residuales.
DEFAULT_FORECAST_K = 2.0
#: Sigma mínimo como fracción de la media, para horas de consumo plano.
MIN_SIGMA_RATIO = 0.02


class StatisticalControlLimitCalculator(ControlLimitCalculator):
    """Bandas Shewhart por hora del día + intervalo de predicción residual."""

    def __init__(
        self,
        *,
        k: float = DEFAULT_K,
        forecast_k: float = DEFAULT_FORECAST_K,
        reference: list[EnergyRecord] | None = None,
        residual_sigma: dict[int, float] | None = None,
        min_sigma_ratio: float = MIN_SIGMA_RATIO,
    ):
        self.k = k
        self.forecast_k = forecast_k
        self.residual_sigma = residual_sigma or {}
        self.min_sigma_ratio = min_sigma_ratio
        # (hora, fin_de_semana) -> (media, sigma)
        self._stats: dict[tuple[int, bool], tuple[float, float]] = {}
        self._fallback: tuple[float, float] = (0.0, 0.0)
        if reference:
            self._fit(reference)

    # -- referencia ----------------------------------------------------------

    def _fit(self, reference: list[EnergyRecord]) -> None:
        cells: dict[tuple[int, bool], list[float]] = defaultdict(list)
        for record in reference:
            key = (record.timestamp.hour, record.timestamp.weekday() >= 5)
            cells[key].append(record.consumption)
        for key, values in cells.items():
            self._stats[key] = (mean(values), stddev(values))
        all_values = [record.consumption for record in reference]
        self._fallback = (mean(all_values), stddev(all_values))

    def _cell(self, ts: datetime) -> tuple[float, float]:
        mu, sigma = self._stats.get(
            (ts.hour, ts.weekday() >= 5), self._stats.get((ts.hour, False), self._fallback)
        )
        return mu, max(sigma, abs(mu) * self.min_sigma_ratio)

    # -- interfaz ControlLimitCalculator -------------------------------------

    def compute_history_limits(self, history: list[EnergyRecord]) -> LimitSeries:
        if not self._stats:
            self._fit(history)
        timestamps: list[datetime] = []
        upper: list[float] = []
        lower: list[float] = []
        for record in history:
            mu, sigma = self._cell(record.timestamp)
            timestamps.append(record.timestamp)
            upper.append(round(mu + self.k * sigma, 2))
            lower.append(round(max(0.0, mu - self.k * sigma), 2))
        return LimitSeries(timestamps=timestamps, upper=upper, lower=lower)

    def compute_forecast_limits(
        self,
        prediction: PredictionResult,
        history: list[EnergyRecord],
    ) -> LimitSeries:
        if not self._stats:
            self._fit(history)
        timestamps: list[datetime] = []
        upper: list[float] = []
        lower: list[float] = []
        for ts, value in zip(prediction.timestamps, prediction.values):
            _, series_sigma = self._cell(ts)
            sigma = self.residual_sigma.get(ts.hour, series_sigma)
            timestamps.append(ts)
            upper.append(round(value + self.forecast_k * sigma, 2))
            lower.append(round(max(0.0, value - self.forecast_k * sigma), 2))
        return LimitSeries(timestamps=timestamps, upper=upper, lower=lower)
