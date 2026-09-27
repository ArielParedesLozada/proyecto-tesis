"""Modelos de dominio: estructuras de datos compartidas por todo el sistema.

Estas estructuras forman parte del sistema "real" y se conservarán tal cual
cuando los componentes mock sean sustituidos por modelos reales.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MachineState(str, Enum):
    """Estado operativo de la máquina."""

    OPERATIVA = "OPERATIVA"
    PARADA = "PARADA"
    MANTENIMIENTO = "MANTENIMIENTO"


class OperationalStatus(str, Enum):
    """Estado operacional del consumo respecto a la banda de control."""

    NORMAL = "NORMAL"
    WARNING = "WARNING"
    ALERT = "ALERT"


@dataclass(frozen=True)
class MachineConditions:
    """Condiciones actuales de la máquina (entrada del modelo de predicción)."""

    timestamp: datetime
    temperature: float  # °C
    production: float  # unidades producidas en el período
    load: float  # carga de la máquina (%)
    state: MachineState


@dataclass(frozen=True)
class EnergyRecord:
    """Registro horario de la máquina (consumo + condiciones asociadas)."""

    timestamp: datetime
    consumption: float  # kWh en el período
    temperature: float
    production: float
    load: float
    state: MachineState


@dataclass(frozen=True)
class PredictionResult:
    """Resultado del modelo de predicción: serie horaria del siguiente turno."""

    shift: str
    start: datetime
    end: datetime
    timestamps: list[datetime]
    values: list[float]  # kWh estimados por hora del siguiente turno

    @property
    def shift_consumption(self) -> float:
        """Consumo total estimado (kWh) para el turno completo."""
        return sum(self.values)


@dataclass(frozen=True)
class LimitSeries:
    """Banda de control (límite superior e inferior) por instante."""

    timestamps: list[datetime]
    upper: list[float]
    lower: list[float]


@dataclass(frozen=True)
class ForecastPoint:
    """Instante del horizonte de predicción con su banda de control y estado."""

    timestamp: datetime
    predicted: float
    upper: float
    lower: float
    status: OperationalStatus


@dataclass(frozen=True)
class DashboardPrediction:
    """Predicción del siguiente turno lista para mostrar en el dashboard."""

    shift: str
    start: datetime
    end: datetime
    consumption: float  # kWh totales estimados para el turno
    lower_bound: float  # extremo inferior del intervalo de la predicción
    upper_bound: float  # extremo superior del intervalo de la predicción
    status: OperationalStatus  # estado agregado del turno predicho
    points: list[ForecastPoint]


@dataclass(frozen=True)
class ShiftInfo:
    """Resumen del turno actual y del turno anterior."""

    current_shift: str
    current_shift_consumption: float  # kWh consumidos en lo que va del turno
    shift_remaining_hours: int
    previous_shift: str
    previous_shift_consumption: float  # kWh totales del turno anterior


@dataclass(frozen=True)
class DashboardData:
    """Payload completo del dashboard (lo que consume el frontend)."""

    generated_at: datetime
    machine_id: str
    machine_description: str
    machine_state: MachineState
    current_conditions: MachineConditions
    current_consumption: float
    current_shift: str
    current_shift_consumption: float
    shift_remaining_hours: int
    previous_shift: str
    previous_shift_consumption: float
    history: list[EnergyRecord]
    history_limits: LimitSeries  # banda de control sobre el consumo real
    history_statuses: list[OperationalStatus]  # estado por registro histórico
    forecast_limits: LimitSeries  # banda de control sobre la predicción
    prediction: DashboardPrediction