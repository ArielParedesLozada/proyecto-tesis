"""Datos simulados de la máquina. **TEMPORAL / MOCK.**

Genera una serie horaria determinista (semilla fija) desde una fecha base
hasta el momento actual. Con la misma semilla, cada hora de la serie tiene
siempre los mismos valores: el comportamiento es reproducible y la aplicación
funciona sin depender de ningún dato externo.

Este módulo se sustituirá por un acceso real a los registros de la máquina.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

from src.domain.data_source import EnergyDataSource
from src.domain.models import EnergyRecord, MachineState, ShiftInfo
from src.domain.shifts import (
    SHIFT_HOURS,
    next_shift_start,
    shift_label,
    shift_start,
)

RNG_SEED = 42
BASE_START = datetime(2026, 1, 1)


def is_maintenance(ts: datetime) -> bool:
    """Ventana de mantenimiento: domingos de madrugada (01:00–04:00)."""
    return ts.weekday() == 6 and 1 <= ts.hour <= 4


def daily_base(hour: int) -> float:
    """Consumo base (kWh/h) según la hora del día: pico ~13h, valle ~3h."""
    return 34.0 + 9.0 * math.sin(2 * math.pi * (hour - 7) / 24)


def _temperature(ts: datetime, rng: random.Random) -> float:
    """Temperatura ambiente simulada (°C): ciclo diurno + estacional + ruido."""
    diurnal = 3.5 * math.sin(2 * math.pi * (ts.hour - 13) / 24)
    seasonal = 6.0 * math.sin(2 * math.pi * (ts.timetuple().tm_yday - 80) / 365)
    return 24.0 + diurnal + seasonal + rng.uniform(-1.0, 1.0)


def _production(ts: datetime, rng: random.Random) -> float:
    """Producción simulada (uds/h): mayor durante el día, nula en mantenimiento."""
    if is_maintenance(ts):
        return 0.0
    base = 360 + 90 * math.sin(2 * math.pi * (ts.hour - 8) / 24)
    return max(0.0, base + rng.gauss(0.0, 20.0))


def _load(ts: datetime, production: float, rng: random.Random) -> float:
    """Carga simulada (%): correlacionada con la producción."""
    if is_maintenance(ts):
        return max(0.0, rng.gauss(10.0, 2.0))
    return max(40.0, min(100.0, 55 + 45 * production / 450 + rng.gauss(0.0, 2.5)))


def _consumption(ts: datetime, temperature: float, production: float, load: float, rng: random.Random) -> float:
    """Consumo simulado (kWh/h) a partir del patrón diario, las condiciones y ruido."""
    if is_maintenance(ts):
        return rng.uniform(2.0, 5.0)
    base = daily_base(ts.hour)
    load_factor = 0.62 + 0.50 * load / 100
    temp_factor = 1 + 0.008 * (temperature - 24.0)
    prod_factor = 0.62 + 0.50 * production / 450
    return max(1.0, base * load_factor * temp_factor * prod_factor + rng.gauss(0.0, 1.6))


class MockDataRepository(EnergyDataSource):
    """Fuente de datos simulada (TEMPORAL). Determinista: misma semilla
    -> los mismos valores para cada hora de la serie."""

    def __init__(self, seed: int = RNG_SEED):
        self._seed = seed
        self._start = BASE_START
        end = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        self._records = self._generate(end)

    # -- generación ---------------------------------------------------------

    def _generate(self, end: datetime) -> list[EnergyRecord]:
        """Serie horaria desde BASE_START hasta `end`, usando una semilla fija."""
        rng = random.Random(self._seed)
        records: list[EnergyRecord] = []
        ts = self._start
        step = timedelta(hours=1)
        while ts <= end:
            state = MachineState.MANTENIMIENTO if is_maintenance(ts) else MachineState.OPERATIVA
            temperature = _temperature(ts, rng)
            production = _production(ts, rng)
            load = _load(ts, production, rng)
            consumption = _consumption(ts, temperature, production, load, rng)
            records.append(
                EnergyRecord(
                    timestamp=ts,
                    consumption=round(consumption, 2),
                    temperature=round(temperature, 1),
                    production=round(production, 1),
                    load=round(load, 1),
                    state=state,
                )
            )
            ts += step
        return records

    def _records_up_to(self, now: datetime) -> list[EnergyRecord]:
        return [r for r in self._records if r.timestamp <= now]

    # -- interfaz EnergyDataSource ------------------------------------------

    def history(self, now: datetime, hours: int) -> list[EnergyRecord]:
        """Últimos `hours` registros horarios hasta el instante `now`."""
        return self._records_up_to(now)[-hours:]

    def shift_info(self, now: datetime) -> ShiftInfo:
        """Consumo parcial del turno actual y consumo total del turno anterior."""
        current_start = shift_start(now)
        current_end = next_shift_start(now)
        previous_start = current_start - timedelta(hours=SHIFT_HOURS)

        current_records = [
            r for r in self._records
            if current_start <= r.timestamp < current_end and r.timestamp <= now
        ]
        previous_records = [
            r for r in self._records
            if previous_start <= r.timestamp < current_start
        ]

        remaining = max(0, int((current_end - now).total_seconds() // 3600))
        return ShiftInfo(
            current_shift=shift_label(now),
            current_shift_consumption=round(sum(r.consumption for r in current_records), 2),
            shift_remaining_hours=remaining,
            previous_shift=shift_label(previous_start),
            previous_shift_consumption=round(sum(r.consumption for r in previous_records), 2),
        )