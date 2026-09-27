"""Interfaz del modelo de predicción energética.

La aplicación depende de esta abstracción, NO de una implementación concreta.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models import EnergyRecord, MachineConditions, PredictionResult


class EnergyPredictionModel(ABC):
    """Modelo que predice el consumo energético del siguiente turno.

    Ejemplos de futuras implementaciones (misma interfaz):
      - StatisticalEnergyModel
      - RandomForestEnergyModel
      - XGBoostEnergyModel
      - LSTMEnergyModel
    """

    @abstractmethod
    def predict(
        self,
        conditions: MachineConditions,
        history: list[EnergyRecord],
    ) -> PredictionResult:
        """Predice el consumo energético (kWh/hora) del siguiente turno a partir
        de las condiciones actuales de la máquina y del historial disponible.
        """
        raise NotImplementedError