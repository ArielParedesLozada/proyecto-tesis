"""Utilidades estadísticas mínimas.

Se usan tanto por el calculador de límites mock como por las implementaciones
estadísticas reales que se incorporen más adelante.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict

from src.domain.models import EnergyRecord


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def stddev(values: list[float]) -> float:
    """Desviación estándar muestral (n-1). Devuelve 0 si hay menos de 2 valores."""
    n = len(values)
    if n < 2:
        return 0.0
    return statistics.stdev(values)


def hourly_stats(records: list[EnergyRecord]) -> dict[int, tuple[float, float]]:
    """Estadísticos (media, desviación) del consumo por hora del día (0-23).

    Sirve de base para calcular bandas de control por hora: p. ej.
    banda = media(hora) ± k * sigma(hora).
    """
    by_hour: dict[int, list[float]] = defaultdict(list)
    for record in records:
        by_hour[record.timestamp.hour].append(record.consumption)

    result: dict[int, tuple[float, float]] = {}
    for hour, values in by_hour.items():
        if len(values) < 2:
            result[hour] = (mean(values), 0.0)
        else:
            result[hour] = (mean(values), stddev(values))
    return result