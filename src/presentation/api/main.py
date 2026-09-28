"""API HTTP del prototipo (FastAPI) + frontend estático.

Sirve los endpoints JSON descritos en el README y el dashboard en "/".

Dos modos de datos, seleccionados con la variable de entorno
`ENERGY_DATA_MODE` (ver `src/demo/wiring.py`):

- `aep` (por defecto): DEMO con el dataset real de AEP (Kaggle), un modelo
  HistGradientBoosting de scikit-learn y bandas de control Shewhart.
- `mock`: los datos simulados originales.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.demo.wiring import build_service, current_mode

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s"
)
LOGGER = logging.getLogger("api")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

# ---------------------------------------------------------------------------
# Wiring de componentes.
# ---------------------------------------------------------------------------
# Las implementaciones se eligen en src/demo/wiring.py; la API y el frontend no
# dependen de ninguna clase concreta. Para conectar el sistema real alcanza con
# registrar otra fuente de datos / modelo / calculadora de límites que cumpla las
# interfaces de src/domain.
# ---------------------------------------------------------------------------
service = build_service()
LOGGER.info("Wiring listo (modo=%s)", current_mode())
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