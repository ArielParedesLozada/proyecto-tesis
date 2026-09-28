"""Fuente de datos REAL de la demo: histórico horario del dataset AEP.

Cumple `src.domain.data_source.EnergyDataSource` leyendo el CSV de Kaggle
(`data/kaggle-dataset.zip`) en lugar de generar datos simulados.

Dos diferencias importantes respecto de la fuente real de producción, ambas
documentadas a propósito porque son las que hacen que la demo sea ejecutable:

1. **Reloj de demo.** El dataset termina el 2018-08-03, así que la serie se
   ancla al último registro disponible en lugar de a `datetime.now()`. Sin esto
   el dashboard pediría 72 h de histórico en 2026 y no habría nada que mostrar.
2. **Condiciones de máquina sintéticas.** AEP sólo trae `Datetime` y `AEP_MW`.
   `temperature`, `production`, `load` y `state` se derivan del calendario y
   del nivel de consumo reciente (ver `src.demo.aep_dataset`), sólo para poder
   preencher `EnergyRecord`/`MachineConditions`. En producción saldrían del
   PLC/SCADA de la máquina.
"""

from __future__ import annotations

import bisect
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from src.demo.aep_dataset import (
    clean_hourly_series,
    hourly_baseline,
    proxy_operational,
    proxy_temperature,
)
from src.domain.data_source import EnergyDataSource
from src.domain.models import EnergyRecord, MachineState, ShiftInfo
from src.domain.shifts import (
    SHIFT_HOURS,
    next_shift_start,
    shift_label,
    shift_start,
)

#: Media (MW) de las 3 horas anteriores al registro, para los proxies operacionales.
TRAILING_WINDOW = 3


class AEPDataSource(EnergyDataSource):
    """Histórico horario real de AEP presentado como registros de máquina."""

    def __init__(
        self,
        zip_path: Path | None = None,
        clock_offset_hours: int = 0,
    ):
        """
        Args:
            zip_path: ZIP con el CSV de AEP (por defecto `data/kaggle-dataset.zip`).
            clock_offset_hours: cuántas horas se adelanta el reloj de la demo
                respecto del último registro. Con 0 (por defecto) el "ahora" es
                el final exacto del dataset; un offset negativo permite mostrar
                un turno a medio consuming sin tocar código.
        """
        self._series, self.report = clean_hourly_series(zip_path)
        self._values = self._series.to_numpy()
        self._timestamps = list(self._series.index)
        self._baseline = hourly_baseline(self._series)
        self._trailing = (
            self._series.shift(1).rolling(TRAILING_WINDOW, min_periods=TRAILING_WINDOW).mean()
        )
        self._last = self._timestamps[-1]
        self._clock = self._last + pd.Timedelta(hours=clock_offset_hours)

    # -- datos de la demo ----------------------------------------------------

    @property
    def series(self) -> pd.Series:
        """Serie horaria completa (índice = timestamp)."""
        return self._series

    def demo_now(self) -> datetime:
        """Instante que la demo considera "ahora" (fin del dataset ± offset)."""
        return self._clock.to_pydatetime()

    def reference_history(self, days: int = 90) -> list[EnergyRecord]:
        """Histórico más largo que el que usa el dashboard.

        Los límites de control necesitan una ventana amplia (un turno son sólo
        8 observaciones) para estimar media y desviación por hora del día.
        """
        end = len(self._timestamps)
        start = max(0, end - days * 24)
        return self._records(start, end)

    # -- construcción de registros -------------------------------------------

    def _record_at(self, position: int) -> EnergyRecord:
        ts = self._timestamps[position]
        consumption = float(self._values[position])
        trailing = self._trailing.iloc[position]
        trailing_value = (
            float(trailing)
            if not np.isnan(trailing)
            else float(self._values[max(0, position - TRAILING_WINDOW) : position + 1].mean())
        )
        baseline = float(self._baseline.get(ts.hour, 0.0))
        production, load = proxy_operational(trailing_value, baseline)
        return EnergyRecord(
            timestamp=ts.to_pydatetime(),
            consumption=round(consumption, 2),
            temperature=round(proxy_temperature(ts), 1),
            production=production,
            load=load,
            state=MachineState.OPERATIVA,
        )

    def _records(self, start: int, end: int) -> list[EnergyRecord]:
        return [self._record_at(i) for i in range(start, end)]

    def _position_at_or_before(self, ts: datetime) -> int:
        """Índice del último registro con timestamp <= `ts` (-1 si no hay)."""
        return bisect.bisect_right(self._timestamps, pd.Timestamp(ts)) - 1

    # -- interfaz EnergyDataSource -------------------------------------------

    def history(self, now: datetime, hours: int) -> list[EnergyRecord]:
        """Últimos `hours` registros, relativos al reloj de la demo."""
        end = self._position_at_or_before(self._effective(now)) + 1
        start = max(0, end - hours)
        return self._records(start, end)

    def shift_info(self, now: datetime) -> ShiftInfo:
        """Consumo parcial del turno actual y consumo total del turno anterior."""
        now = self._effective(now)
        current_start = shift_start(now)
        current_end = next_shift_start(now)
        previous_start = current_start - timedelta(hours=SHIFT_HOURS)

        current_end_index = self._position_at_or_before(current_end - timedelta(hours=1)) + 1
        current_start_index = max(0, self._position_at_or_before(current_start) + 1)
        previous_start_index = max(0, self._position_at_or_before(previous_start) + 1)

        current = float(self._values[current_start_index:current_end_index].sum())
        previous = float(self._values[previous_start_index:current_start_index].sum())
        remaining = max(0, int((current_end - now).total_seconds() // 3600))

        return ShiftInfo(
            current_shift=shift_label(now),
            current_shift_consumption=round(current, 2),
            shift_remaining_hours=remaining,
            previous_shift=shift_label(previous_start),
            previous_shift_consumption=round(previous, 2),
        )

    def _effective(self, now: datetime) -> datetime:
        """Ancla `now` al final del dataset (reloj de la demo)."""
        return min(now, self.demo_now())
