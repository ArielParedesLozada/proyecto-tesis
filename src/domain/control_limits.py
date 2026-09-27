"""Interfaz del calculador de límites de control operacional.

Separa el cálculo de las bandas de control del resto del sistema para poder
sustituir la implementación mock por métodos estadísticos reales más adelante.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models import EnergyRecord, LimitSeries, PredictionResult


class ControlLimitCalculator(ABC):
    """Calcula las bandas de control (límite superior e inferior) del consumo."""

    @abstractmethod
    def compute_history_limits(self, history: list[EnergyRecord]) -> LimitSeries:
        """Banda de control para el consumo real histórico (una por registro).

        En el sistema real correspondería a un gráfico de control
        (p. ej. Shewhart: media ± k·sigma por hora del día).
        """

    @abstractmethod
    def compute_forecast_limits(
        self,
        prediction: PredictionResult,
        history: list[EnergyRecord],
    ) -> LimitSeries:
        """Banda de control dinámica (por instante) para el horizonte predicho.

        En el sistema real correspondería al intervalo de predicción / banda
        de tolerancia del modelo.
        """