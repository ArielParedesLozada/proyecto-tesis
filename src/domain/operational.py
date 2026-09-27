"""Lógica de estado operacional: NORMAL / WARNING / ALERT.

Regla (sencilla y documentada; se puede ajustar o sustituir por la política
real del proyecto sin tocar el resto del sistema):

- ALERT:   el consumo está FUERA de la banda [lower, upper].
- WARNING: el consumo está dentro de la banda pero a menos de un 10% del
           ancho de la banda respecto a uno de los límites.
- NORMAL:  cualquier otro caso.
"""

from __future__ import annotations

from src.domain.models import OperationalStatus

WARNING_MARGIN = 0.10  # fracción del ancho de la banda para declarar WARNING


def classify_consumption(consumption: float, lower: float, upper: float) -> OperationalStatus:
    """Clasifica un consumo respecto a su banda de control."""
    if upper < lower:
        raise ValueError(f"upper ({upper}) no puede ser menor que lower ({lower})")

    if consumption < lower or consumption > upper:
        return OperationalStatus.ALERT

    span = upper - lower
    if span <= 0:
        return OperationalStatus.NORMAL

    near_lower = consumption <= lower + WARNING_MARGIN * span
    near_upper = consumption >= upper - WARNING_MARGIN * span
    if near_lower or near_upper:
        return OperationalStatus.WARNING
    return OperationalStatus.NORMAL


def aggregate_status(statuses: list[OperationalStatus]) -> OperationalStatus:
    """Peor estado de una lista (ALERT > WARNING > NORMAL)."""
    if OperationalStatus.ALERT in statuses:
        return OperationalStatus.ALERT
    if OperationalStatus.WARNING in statuses:
        return OperationalStatus.WARNING
    return OperationalStatus.NORMAL