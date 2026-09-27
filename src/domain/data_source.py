"""Abstracción de la fuente de datos de la máquina.

El mock implementa esta interfaz con datos simulados. En el sistema real se
sustituirá por una implementación que lea los registros de la máquina / BD.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.models import EnergyRecord, ShiftInfo


class EnergyDataSource(ABC):
    """Provee los registros de la máquina al resto del sistema."""

    @abstractmethod
    def history(self, now: datetime, hours: int) -> list[EnergyRecord]:
        """Últimos `hours` registros horarios de la máquina hasta el instante `now`."""

    @abstractmethod
    def shift_info(self, now: datetime) -> ShiftInfo:
        """Resumen del turno actual (consumo parcial) y del turno anterior."""