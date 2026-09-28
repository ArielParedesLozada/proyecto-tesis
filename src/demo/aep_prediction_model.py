"""Modelo de predicción REAL de la demo AEP (scikit-learn).

Cumple `src.domain.prediction_model.EnergyPredictionModel` y sustituye a
`src.mocks.mock_prediction_model.MockEnergyPredictionModel` en el wiring.

Usa el mismo modelo entrenado por `scripts/train_aep_model.py`:

- Si existe `artifacts/aep_model.joblib`, lo carga (arranque instantáneo).
- Si no existe o es incompatible, se entrena en memoria al vuelo, de modo que
  la demo funciona end-to-end sin ningún paso previo.

La predicción del turno siguiente (8 horas) es **recursiva**: los lags de las
horas 2..8 se alimentan con las predicciones ya emitidas, que es exactamente el
procedimiento que evalúa el backtest del script de entrenamiento.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

from src.demo.aep_dataset import DEFAULT_ZIP_PATH
from src.demo.aep_training import (
    load_artifact,
    recursive_forecast,
    run_training,
)
from src.domain.models import EnergyRecord, MachineConditions, PredictionResult
from src.domain.prediction_model import EnergyPredictionModel
from src.domain.shifts import SHIFT_HOURS, next_shift_start, shift_label

LOGGER = logging.getLogger("demo.aep.model")
#: Hours of history the model needs (lags up to 48 h + 72 h rolling means).
CONTEXT_HOURS = 72


class AEPGradientBoostingModel(EnergyPredictionModel):
    """Regresión con gradient boosting sobre el histórico real de AEP."""

    def __init__(
        self,
        artifact_path: Path | None = None,
        zip_path: Path | None = None,
    ):
        self._zip_path = Path(zip_path) if zip_path else DEFAULT_ZIP_PATH
        self._model, self._origin = self._load_or_train(artifact_path)

    # -- construcción --------------------------------------------------------

    def _load_or_train(self, artifact_path: Path | None) -> tuple[object, str]:
        try:
            payload = load_artifact(artifact_path)
        except Exception as error:  # noqa: BLE001 - cualquier fallo => reentrenar
            LOGGER.warning(
                "Sin artefacto de entrenamiento utilizable (%s); entrenando en memoria.",
                error,
            )
            model, _metrics, _report = run_training(zip_path=self._zip_path)
            return model, "entrenado en memoria"
        LOGGER.info("Modelo cargado desde el artefacto de entrenamiento.")
        return payload["model"], "artefacto"

    @property
    def origin(self) -> str:
        """Origen del modelo: `artefacto` o `entrenado en memoria`."""
        return self._origin

    # -- interfaz EnergyPredictionModel --------------------------------------

    def predict(
        self,
        conditions: MachineConditions,
        history: list[EnergyRecord],
    ) -> PredictionResult:
        start = next_shift_start(conditions.timestamp)
        end = start + timedelta(hours=SHIFT_HOURS)
        timestamps = [start + timedelta(hours=i) for i in range(SHIFT_HOURS)]

        if len(history) < CONTEXT_HOURS:
            raise ValueError(
                f"El modelo necesita al menos {CONTEXT_HOURS} h de histórico "
                f"(recibió {len(history)})"
            )

        values = recursive_forecast(
            self._model,
            [record.consumption for record in history[-CONTEXT_HOURS:]],
            [record.timestamp for record in history[-CONTEXT_HOURS:]],
            (conditions.temperature, conditions.production, conditions.load),
            start,
        )

        return PredictionResult(
            shift=shift_label(start),
            start=start,
            end=end,
            timestamps=timestamps,
            values=[round(value, 2) for value in values],
        )
