"""Modelo de predicción SIMULADO. **TEMPORAL / MOCK.**

Produce una predicción razonable y determinista del consumo del siguiente
turno a partir de las condiciones actuales y del historial.

Reemplazo futuro: crear una clase con la misma interfaz
(src.domain.prediction_model.EnergyPredictionModel), p. ej.:

    - StatisticalEnergyModel
    - RandomForestEnergyModel
    - XGBoostEnergyModel
    - LSTMEnergyModel

y cambiar únicamente la línea de "wiring" en src/presentation/api/main.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.data.mock_data import daily_base, is_maintenance
from src.domain.models import EnergyRecord, MachineConditions, PredictionResult
from src.domain.prediction_model import EnergyPredictionModel
from src.domain.shifts import SHIFT_HOURS, next_shift_start, shift_label
from src.domain.statistics import mean


class MockEnergyPredictionModel(EnergyPredictionModel):
    """Predicción mock: patrón diario de consumo escalado por las condiciones
    actuales de la máquina y por el nivel reciente del histórico."""

    def predict(
        self,
        conditions: MachineConditions,
        history: list[EnergyRecord],
    ) -> PredictionResult:
        start = next_shift_start(conditions.timestamp)
        end = start + timedelta(hours=SHIFT_HOURS)
        timestamps = [start + timedelta(hours=i) for i in range(SHIFT_HOURS)]

        # Nivel reciente (últimas 6 horas) para corregir el patrón base.
        recent = history[-6:]
        recent_avg = mean([r.consumption for r in recent]) if recent else 40.0
        base_recent = mean([daily_base(r.timestamp.hour) for r in recent])
        base_recent = base_recent if base_recent > 0 else daily_base(start.hour)
        drift = max(0.85, min(1.15, recent_avg / base_recent))

        # Factores según las condiciones actuales de la máquina.
        temp_factor = 1 + 0.008 * (conditions.temperature - 24.0)
        load_factor = 0.62 + 0.50 * conditions.load / 100
        prod_factor = 0.62 + 0.50 * conditions.production / 450

        values: list[float] = []
        for ts in timestamps:
            if is_maintenance(ts):
                # Mantenimiento programado: consumo bajo.
                value = 3.5 + (ts.day % 3) * 0.4
            else:
                value = daily_base(ts.hour) * temp_factor * load_factor * prod_factor * drift
                # Pequeña variación determinista por hora (sin aleatoriedad).
                value += ((ts.hour * 31 + ts.day * 7) % 7 - 3) * 0.25
            values.append(round(max(1.0, value), 2))

        return PredictionResult(
            shift=shift_label(start),
            start=start,
            end=end,
            timestamps=timestamps,
            values=values,
        )