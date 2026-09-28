"""Wiring de la demo: elige qué implementación de cada interfaz se inyecta.

Un único lugar decide qué fuente de datos, qué modelo de predicción y qué
calculador de límites se usan, para que `src/presentation/api/main.py` no tenga
que conocer las clases concretas.

Modos (variable de entorno `ENERGY_DATA_MODE`):

- `aep` (por defecto): demo con el dataset real de AEP (Kaggle) y modelo
  entrenado con scikit-learn. Es lo que se quiere mostrar en la demostración.
- `mock`: los mocks simulados originales, útiles para comparar y para develops
  sin dataset.

    ENERGY_DATA_MODE=mock python run.py

En ambos casos la API REST y el dashboard son exactamente los mismos.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.application.prediction_service import PredictionService

LOGGER = logging.getLogger("demo.wiring")

MODE_ENV = "ENERGY_DATA_MODE"
MODE_AEP = "aep"
MODE_MOCK = "mock"
DEFAULT_MODE = MODE_AEP
VALID_MODES = (MODE_AEP, MODE_MOCK)

#: Días de histórico usados para estimar media y sigma de las bandas de control.
REFERENCE_DAYS = 90
#: Identidad de la "máquina" en la demo: el dataset es la red de AEP, no la máquina.
AEP_MACHINE_ID = "AEP (demo)"
AEP_MACHINE_DESCRIPTION = "American Electric Power · consumo horario MW"


def current_mode() -> str:
    """Modo configurado por entorno (por defecto, la demo AEP)."""
    mode = os.environ.get(MODE_ENV, DEFAULT_MODE).strip().lower()
    if mode not in VALID_MODES:
        LOGGER.warning(
            "Valor no válido para %s=%r; se usa %r. Valores admitidos: %s",
            MODE_ENV,
            mode,
            DEFAULT_MODE,
            ", ".join(VALID_MODES),
        )
        return DEFAULT_MODE
    return mode


def _build_aep_service(zip_path: Path | None = None, artifact_path: Path | None = None):
    """Demo end-to-end con datos reales de AEP y modelo entrenado."""
    from src.demo.aep_data_source import AEPDataSource
    from src.demo.aep_prediction_model import AEPGradientBoostingModel
    from src.demo.aep_training import load_artifact
    from src.demo.statistical_control_limits import StatisticalControlLimitCalculator

    data_source = AEPDataSource(zip_path)
    report = data_source.report
    LOGGER.info(
        "Dataset AEP: %d registros limpios (%s → %s); %d duplicados y %d horas interpoladas",
        report["clean_rows"],
        report["start"],
        report["end"],
        report["duplicated_timestamps"],
        report["filled_hours"],
    )

    model = AEPGradientBoostingModel(artifact_path=artifact_path, zip_path=zip_path)

    # σ residual por hora del backtest: si hay artefacto, se reutiliza para que
    # el ancho de las bandas de predición sea el error real del modelo.
    residual_sigma: dict[int, float] = {}
    try:
        payload = load_artifact(artifact_path)
        residual_sigma = {
            int(hour): float(value)
            for hour, value in (payload.get("metrics", {}).get("residual_sigma_by_hour") or {}).items()
        }
    except Exception as error:  # noqa: BLE001 - las bandas pueden igual calcularse
        LOGGER.info("Sin σ residual del backtest (%s); se usará σ de la serie.", error)

    limits_calculator = StatisticalControlLimitCalculator(
        reference=data_source.reference_history(days=REFERENCE_DAYS),
        residual_sigma=residual_sigma,
    )

    LOGGER.info(
        "Demo AEP lista: fuente=%d filas, modelo=%s, bandas de referencia=%d días",
        report["clean_rows"],
        model.origin,
        REFERENCE_DAYS,
    )
    return PredictionService(
        model=model,
        limits_calculator=limits_calculator,
        data_source=data_source,
        machine_id=AEP_MACHINE_ID,
        machine_description=AEP_MACHINE_DESCRIPTION,
    )


def _build_mock_service() -> PredictionService:
    """Wiring original, con datos simulados."""
    from src.data.mock_data import MockDataRepository
    from src.mocks.mock_control_limits import MockControlLimitCalculator
    from src.mocks.mock_prediction_model import MockEnergyPredictionModel

    LOGGER.info("Modo mock: datos simulados (sin dataset AEP).")
    return PredictionService(
        model=MockEnergyPredictionModel(),
        limits_calculator=MockControlLimitCalculator(),
        data_source=MockDataRepository(),
    )


def build_service(mode: str | None = None) -> PredictionService:
    """Construye el `PredictionService` con las implementaciones del modo elegido."""
    mode = (mode or current_mode()).strip().lower()
    if mode == MODE_AEP:
        return _build_aep_service()
    if mode == MODE_MOCK:
        return _build_mock_service()
    raise ValueError(f"Modo desconocido: {mode!r}. Usá {MODE_AEP} o {MODE_MOCK}.")
