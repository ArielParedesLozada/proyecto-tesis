"""Servicio de predicción: orquesta modelo de predicción + límites + datos.

Este servicio es parte REUTILIZABLE del sistema final: depende de las
abstracciones del dominio (EnergyPredictionModel, ControlLimitCalculator,
EnergyDataSource), no de las implementaciones mock.
"""

from __future__ import annotations

from datetime import datetime

from src.domain.control_limits import ControlLimitCalculator
from src.domain.data_source import EnergyDataSource
from src.domain.models import (
    DashboardData,
    DashboardPrediction,
    ForecastPoint,
    MachineConditions,
)
from src.domain.operational import aggregate_status, classify_consumption
from src.domain.prediction_model import EnergyPredictionModel

# Ventana histórica mostrada en el dashboard (en horas).
HISTORY_HOURS = 72


class PredictionService:
    """Compone condiciones actuales, historial, predicción y banda de control."""

    def __init__(
        self,
        *,
        model: EnergyPredictionModel,
        limits_calculator: ControlLimitCalculator,
        data_source: EnergyDataSource,
        machine_id: str = "Máquina 01",
        machine_description: str = "Inyectora de suelas — Línea A",
    ):
        self._model = model
        self._limits_calculator = limits_calculator
        self._data_source = data_source
        self._machine_id = machine_id
        self._machine_description = machine_description

    def dashboard(self, now: datetime | None = None) -> DashboardData:
        """Snapshot completo para el dashboard: historial + predicción + límites."""
        now = now or datetime.now()
        history = self._data_source.history(now, hours=HISTORY_HOURS)
        if not history:
            raise RuntimeError("No hay datos históricos disponibles")

        current = history[-1]
        conditions = MachineConditions(
            timestamp=current.timestamp,
            temperature=current.temperature,
            production=current.production,
            load=current.load,
            state=current.state,
        )

        # ---- Punto de sustitución (modelo real) ----------------------------
        prediction = self._model.predict(conditions, history)
        # --------------------------------------------------------------------

        # ---- Punto de sustitución (cálculo de límites real) ----------------
        history_limits = self._limits_calculator.compute_history_limits(history)
        forecast_limits = self._limits_calculator.compute_forecast_limits(prediction, history)
        # --------------------------------------------------------------------

        history_statuses = [
            classify_consumption(record.consumption, lower, upper)
            for record, lower, upper in zip(
                history, history_limits.lower, history_limits.upper
            )
        ]

        points = [
            ForecastPoint(
                timestamp=timestamp,
                predicted=value,
                upper=upper,
                lower=lower,
                status=classify_consumption(value, lower, upper),
            )
            for timestamp, value, upper, lower in zip(
                prediction.timestamps,
                prediction.values,
                forecast_limits.upper,
                forecast_limits.lower,
            )
        ]

        shift_info = self._data_source.shift_info(now)

        return DashboardData(
            generated_at=now,
            machine_id=self.machine_id,
            machine_description=self.machine_description,
            machine_state=current.state,
            current_conditions=conditions,
            current_consumption=current.consumption,
            current_shift=shift_info.current_shift,
            current_shift_consumption=shift_info.current_shift_consumption,
            shift_remaining_hours=shift_info.shift_remaining_hours,
            previous_shift=shift_info.previous_shift,
            previous_shift_consumption=shift_info.previous_shift_consumption,
            history=history,
            history_limits=history_limits,
            history_statuses=history_statuses,
            forecast_limits=forecast_limits,
            prediction=DashboardPrediction(
                shift=prediction.shift,
                start=prediction.start,
                end=prediction.end,
                consumption=prediction.shift_consumption,
                # Intervalo del TOTAL del turno: suma de las bandas horarias
                # (cada hora se trata como fuente independiente de incertidumbre).
                lower_bound=round(sum(point.lower for point in points), 2),
                upper_bound=round(sum(point.upper for point in points), 2),
                status=aggregate_status([point.status for point in points]),
                points=points,
            ),
        )

    @property
    def machine_id(self) -> str:
        return self._machine_id

    @property
    def machine_description(self) -> str:
        return self._machine_description