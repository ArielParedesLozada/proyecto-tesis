"""API HTTP del prototipo (FastAPI) + frontend estático.

Sirve los endpoints JSON descritos en el README y el dashboard en "/".
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.application.prediction_service import PredictionService
from src.data.mock_data import MockDataRepository
from src.mocks.mock_control_limits import MockControlLimitCalculator
from src.mocks.mock_prediction_model import MockEnergyPredictionModel

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

# ---------------------------------------------------------------------------
# Wiring de componentes.
# ---------------------------------------------------------------------------
# PUNTO DE SUSTITUCIÓN DE MOCKS POR MODELOS REALES.
# Para conectar el sistema real solo hay que cambiar estas tres líneas:
#
#   data_source       = RealDataSource(...)                  # registros reales
#   model             = RandomForestEnergyModel(...)         # Statistical/XGB/LSTM...
#   limits_calculator = StatisticalControlLimitCalculator(...)
#
# El servicio, la API y el frontend no necesitan ningún cambio.
# ---------------------------------------------------------------------------
data_source = MockDataRepository()
model = MockEnergyPredictionModel()
limits_calculator = MockControlLimitCalculator()

service = PredictionService(
    model=model,
    limits_calculator=limits_calculator,
    data_source=data_source,
)
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Energy Control System — Mock",
    description=(
        "Prototipo funcional de predicción y control operacional del "
        "consumo energético de una máquina industrial."
    ),
    version="0.1.0",
)


@app.get("/api/machine/status")
def machine_status():
    data = service.dashboard()
    return {
        "machine_id": data.machine_id,
        "machine_description": data.machine_description,
        "state": data.machine_state,
        "current_conditions": data.current_conditions,
        "current_consumption": data.current_consumption,
        "current_shift": data.current_shift,
    }


@app.get("/api/energy/history")
def energy_history():
    data = service.dashboard()
    return {
        "machine_id": data.machine_id,
        "records": data.history,
        "limits": data.history_limits,
        "statuses": data.history_statuses,
    }


@app.get("/api/energy/prediction")
def energy_prediction():
    return {"prediction": service.dashboard().prediction}


@app.get("/api/energy/control-limits")
def energy_control_limits():
    data = service.dashboard()
    return {
        "history_limits": data.history_limits,
        "forecast_limits": data.forecast_limits,
    }


@app.get("/api/dashboard")
def dashboard():
    """Payload único con todo lo que necesita el dashboard."""
    return service.dashboard()


# Frontend estático. Se registra al final para que /api/* tenga prioridad.
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")