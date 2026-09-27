"""Definición de turnos de producción (3 turnos de 8 horas)."""

from __future__ import annotations

from datetime import datetime, timedelta

SHIFT_HOURS = 8
SHIFT_NAMES = {0: "Turno A", 1: "Turno B", 2: "Turno C"}
# Turno A: 00:00–08:00 · Turno B: 08:00–16:00 · Turno C: 16:00–24:00


def shift_index(dt: datetime) -> int:
    """Índice del turno (0, 1 o 2) al que pertenece el instante dado."""
    return dt.hour // SHIFT_HOURS


def shift_start(dt: datetime) -> datetime:
    """Inicio (fecha-hora) del turno al que pertenece el instante dado."""
    return dt.replace(minute=0, second=0, microsecond=0).replace(
        hour=(dt.hour // SHIFT_HOURS) * SHIFT_HOURS
    )


def next_shift_start(dt: datetime) -> datetime:
    """Inicio del turno siguiente al que pertenece el instante dado."""
    return shift_start(dt) + timedelta(hours=SHIFT_HOURS)


def shift_label(dt: datetime) -> str:
    """Nombre del turno al que pertenece el instante dado."""
    return SHIFT_NAMES[shift_index(dt)]