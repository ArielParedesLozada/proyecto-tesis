# PROYECTO DE INVESTIGACION

Crear un sistema web de prediccion y control operacional para una maquina en Plasticaucho

## OBJETIVO

Desarrollar un sistema de prediccion en base alos registros obtenidos de la maquina de Plasticaucho para tener un control operacional sobre la energia

## REQUERIMIENTOS FUNCIONALES

- Definir una arquitectura, capas y demas cosas para poder entrenar modelos de IA para la prediccion energetica
- Tener un modelo que, dadas las condiciones actuales de la maquina, pueda predecir el consumo energetico del siguiente turno
- Poder ver la prediccion del consumo energetico sobrepuesta sobre el consumo real
- En esa prediccion del consumo, ver dos lineas, una superior y otra inferior, para tener limites de consumo energetico
- Las lineas de consumo energetico se calculan mediante formulas estadisticas

## ESTRUCTURA

El proyecto sigue una arquitectura modular en capas inspirada en Clean Architecture / Domain-Driven Design, separando claramente el dominio de negocio, la lógica de aplicación, las fuentes de datos, los mocks y las capas de presentación (API y Frontend). Esto facilita la comprensión por parte de LLMs y desarrolladores, permitiendo además sustituir componentes simulados (mocks) por modelos de Machine Learning reales y bases de datos sin alterar la lógica central.

```console
src/
├── application/                  # Capa de aplicación
│   └── prediction_service.py     # Orquesta el modelo de predicción, cálculo de límites estadísticos y repositorio de datos para generar el payload del dashboard.
├── data/                         # Capa de acceso a datos (abstracción / repositorios)
│   └── mock_data.py              # Repositorio de datos históricos y turnos (actualmente con mocks/datos simulados).
├── demo/                         # DEMO con datos reales de AEP + modelo sklearn (ver sección DEMO; se borra al pasar a producción)
│   ├── aep_dataset.py            # Lectura del dataset, limpieza, interpolación de huecos e ingeniería de variables.
│   ├── aep_data_source.py        # EnergyDataSource real (histórico de AEP, reloj de demo, proxies de condiciones).
│   ├── aep_prediction_model.py   # EnergyPredictionModel real (HistGradientBoosting de scikit-learn).
│   ├── statistical_control_limits.py # ControlLimitCalculator real (bandas Shewhart + intervalo de predicción).
│   ├── aep_training.py           # Entrenamiento, backtesting y persistencia del modelo.
│   └── wiring.py                 # Selección de implementaciones según ENERGY_DATA_MODE.
├── domain/                       # Capa de dominio (lógica de negocio central y contratos)
│   ├── models.py                 # Entidades y DTOs inmutables (MachineConditions, EnergyRecord, DashboardData, etc.).
│   ├── data_source.py            # Interfaces/contratos abstractos para fuentes de datos.
│   ├── prediction_model.py       # Interfaz abstracta para modelos de predicción energética.
│   ├── control_limits.py         # Interfaz abstracta para calculadores de límites de control estadístico.
│   ├── operational.py            # Reglas de negocio para clasificación de consumo (Normal, Warning, Alert) y agregación de estados.
│   ├── shifts.py                 # Lógica de gestión de turnos de trabajo industriales.
│   └── statistics.py             # Funciones estadísticas (medias, desviaciones estándar, bandas de control).
├── mocks/                        # Implementaciones simuladas (Mocks) para desarrollo y pruebas
│   ├── mock_prediction_model.py  # Genera predicciones horarias simuladas para el siguiente turno.
│   └── mock_control_limits.py    # Calcula bandas de control estadístico (superior/inferior) basadas en medias y desvíos.
└── presentation/                 # Capa de presentación (Backend API y Frontend UI)
    ├── api/                      # Backend REST (FastAPI)
    │   └── main.py               # Endpoints REST (/api/dashboard, /api/machine/status, etc.) y punto de wiring de dependencias.
    └── web/                      # Frontend estático / Dashboard interactivo
        ├── index.html            # Interfaz visual principal del dashboard industrial.
        ├── app.js                # Lógica cliente para peticiones asíncronas a la API.
        ├── chart.js              # Renderizado de gráficos de consumo, predicción y bandas de control.
        └── styles.css            # Estilos visuales de la interfaz.
root/
├── run.py                        # Punto de entrada local para arrancar el servidor Uvicorn.
├── scripts/
│   └── train_aep_model.py        # Script de entrenamiento y backtest del modelo de la demo.
├── data/
│   └── kaggle-dataset.zip        # Dataset "Unprocessed Energy Consumption Data (AEP)" (Kaggle).
├── artifacts/                    # Generado por el entrenamiento: aep_model.joblib + aep_metrics.json.
├── devenv.nix / devenv.yaml      # Configuración de entorno de desarrollo reproducible (Nix/devenv).
└── requirements.txt              # Dependencias de Python (FastAPI, uvicorn, pandas, scikit-learn, etc.).
```

### Funcionalidad y Guía para LLMs y Extensiones
- **Punto Central de Wiring (`src/presentation/api/main.py`):** Los componentes de datos, predicción y límites se inyectan en `PredictionService`. Para conectar un modelo de IA real (ej. modelos basados en Machine Learning o Deep Learning) o una base de datos de históricos, solo se requiere implementar las interfaces del dominio (`EnergyDataSource`, `EnergyPredictionModel`, `ControlLimitCalculator`) y cambiar la construcción en `src/demo/wiring.py`, sin modificar la API ni el frontend.
- **Dominio Aislado (`src/domain/`):** Contiene el núcleo conceptual (modelos de datos inmutables y reglas operacionales independientes de frameworks externos), lo que permite a los LLMs razonar de manera precisa sobre la lógica de control energético y los estados operativos (`OPERATIVA`, `PARADA`, `MANTENIMIENTO`, `NORMAL`, `WARNING`, `ALERT`).

## DEMO

Demo funcional end-to-end que reemplaza los mocks por implementaciones **reales**: datos históricos reales, modelo de ML entrenado y límites de control estadísticos. Sirve para mostrar cómo funcionaría el sistema con datos de verdad.

**No es el sistema final.** Es una prueba de concepto: los datos son de una red eléctrica (AEP), no de la máquina, y varias piezas están adaptadas para que la demo funcione. Al conectar la máquina de Plasticaucho se borra `src/demo/` y se implementan las mismas interfaces con datos reales.

### Cómo probarla

```console
# 1. Dependencias (dentro del shell de devenv)
uv pip install -r requirements.txt

# 2. (Opcional) Entrenar el modelo y ver las métricas. Sin este paso la demo
#    funciona igual: el modelo se entrena en memoria al arrancar.
python scripts/train_aep_model.py

# 3. Arrancar
python run.py            # http://127.0.0.1:8000

# 4. Comparar contra los mocks simulados originales
ENERGY_DATA_MODE=mock python run.py
```

El contrato de la API no cambia: mismos endpoints (`/api/dashboard`, `/api/machine/status`, `/api/energy/history`, `/api/energy/prediction`, `/api/energy/control-limits`) y mismo dashboard.

### El dataset

"Unprocessed Energy Consumption Data (AEP)" de Kaggle, dentro de `data/kaggle-dataset.zip`.

| | |
|---|---|
| Formato | `Datetime,AEP_MW` con fecha `M/D/YYYY H:MM` (sin AM/PM) |
| Filas crudas | 120 114 |
| Rango | 2004-10-01 00:00 → 2018-08-03 00:00 |
| Valores | 9 581 – 25 164 (MW) |
| Nulos | 0 |
| Timestamps duplicados | 4 (caída de hora de verano) |
| Horas ausentes | 1 187, siempre en rachas de 1–2 h |

Preprocesamiento aplicado (`src/demo/aep_dataset.py`): parseo de la fecha, dedupe de duplicados, reindexado a serie horaria continua e **interpolación de los 1 187 huecos** (100 % de los casos, porque ninguna racha supera las 2 h). Resultado: 121 297 horas.

### Archivos de la demo

| Archivo | Interfaz que cumple | Qué hace |
|---|---|---|
| `src/demo/aep_dataset.py` | — | Carga del ZIP, limpieza, interpolación e ingeniería de variables. Única implementación de features, compartida por entrenamiento y runtime. |
| `src/demo/aep_data_source.py` | `EnergyDataSource` | Histórico real de AEP como `EnergyRecord`, con reloj de demo y proxies de condiciones. |
| `src/demo/aep_prediction_model.py` | `EnergyPredictionModel` | Carga `artifacts/aep_model.joblib`; si no existe, entrena en memoria. |
| `src/demo/statistical_control_limits.py` | `ControlLimitCalculator` | Bandas Shewhart y intervalo de predicción. |
| `src/demo/aep_training.py` | — | `fit_model`, `recursive_forecast`, `backtest`, persistencia. |
| `src/demo/wiring.py` | — | Elige implementaciones según `ENERGY_DATA_MODE`. |
| `scripts/train_aep_model.py` | — | Entrenamiento + backtest + métricas + artefacto. |

**Ninguna interfaz de `src/domain/` fue modificada**: las clases nuevas implementan los contratos existentes, que es justamente lo que la arquitectura permite.

### El modelo

`HistGradientBoostingRegressor` de scikit-learn (regresión, sin GPU, entrena en segundos). Variables de entrada:

- **Calendario:** hora, día de la semana, mes, finde y armónicos sin/cos de hora, día de la semana y día del año.
- ** lags:** 1, 2, 3, 24 y 48 horas.
- **Estadísticos móviles:** media de 6/24/72 h, desviación y máximo de 24 h.
- **Condiciones operacionales:** temperatura, producción y carga (proxies, ver abajo).

La predicción del turno siguiente (8 h) es **recursiva**: los lags de las horas 2..8 se alimentan con las predicciones ya emitidas. El código de forecast es el mismo en entrenamiento y en runtime, por eso las métricas del backtest son representativas.

### Límites de control

- **Histórico:** gráfico de control Shewhart por hora del día, separando finde de día laborable: banda = `μ(h) ± 3·σ(h)`, con μ y σ estimados sobre los últimos 90 días.
- **Predicción:** intervalo alrededor del valor predicho cuyo ancho es la **σ residual por hora medida en el backtest**, no la desviación de la serie. Así la banda representa el error real del modelo.

### Métricas obtenidas

Backtest sobre 240 turnos de los últimos 90 días, con el modelo que **no vio** ese período:

| Métrica | MAE | MAPE | RMSE |
|---|---|---|---|
| Consumo horario | 2 080.88 | 14.03 % | 2 584.14 |
| Total del turno (8 h) | 15 832.30 | 13.43 % | — |

Referencia: la mediana horaria de la serie es 15 947. El detalle por hora queda en `artifacts/aep_metrics.json`.

### Modos de ejecución

| `ENERGY_DATA_MODE` | Fuente de datos | Modelo | Límites |
|---|---|---|---|
| `aep` (default) | Histórico real de AEP | HistGradientBoosting | Shewhart + intervalo de predicción |
| `mock` | `src/data/mock_data.py` (simulado) | `MockEnergyPredictionModel` | Márgenes fijos del mock |

### Limitaciones conocidas de la demo

- **Unidades:** AEP viene en MW (potencia media horaria) y el frontend etiqueta "kWh". El valor numérico se muestra sin convertir.
- **Reloj de demo:** la serie se ancla al final del dataset (2018-08-03 00:00), no a la fecha real. Como cae justo en el inicio del Turno A, el KPI de consumo del turno en curso muestra 0. `AEPDataSource(clock_offset_hours=...)` permite ver un turno a medias.
- **Condiciones de máquina sintéticas:** el dataset sólo trae fecha y consumo, así que `temperature`, `production` y `load` se derivan del calendario y del nivel de consumo reciente. Nunca usan el valor que se predice, para no filtrar información del objetivo.
- **State siempre `OPERATIVA`:** AEP es consumo de red y no tiene estados de máquina.
- **Entrenamiento con "teacher forcing":** las variables de lags del conjunto de entrenamiento usan valores reales, mientras que en runtime la hora 2 en adelante usa predicciones. Es la fuente clásica de optimismo en el backtest, y por eso el modelo se evalúa recursivamente.
- **Precisión:** el MAPE de 14 % es mejorable. La causa probable es que la ventana de 72 h que fija `HISTORY_HOURS` en `application/prediction_service.py` deja fuera el predictor más fuerte de AEP: el valor de la misma hora en días anteriores (lag 72/168). Subir esa ventana a 168 h desbloquearía esas variables, a cambio de mostrar 7 días en el gráfico en vez de 3.
- **El modelo reentrenado usa toda la serie**, incluidas las horas del holdout, mientras que las métricas informadas vienen del modelo que no las vio: las métricas son una estimación conservadora.

### Qué habría que cambiar para producción

1. **Fuente de datos:** reemplazar `AEPDataSource` por un `EnergyDataSource` que lea el PLC/SCADA o la base de datos real de la máquina. Es el cambio de mayor impacto.
2. **Condiciones reales:** `temperature`, `production`, `load` y `state` deben venir de la máquina, no de proxies sintéticos.
3. **Unidades:** kWh reales en `EnergyRecord.consumption` (encajar la conversión en la fuente de datos, no en el dominio).
4. **Reloj real:** eliminar el reloj de demo y usar la hora actual, con la serie histórica llegando por push/streaming en vez de un CSV.
5. **Modelo:** reentrenar con datos de la máquina, comparar contra una línea base y versionar el modelo elegido (XGBoost/LightGBM o una red recurrente si el volumen lo justifica). Las variables y el entrenamiento se reescriben; las interfaces no.
6. **Límites:** recalibrar `k` y el intervalo de predicción con la variabilidad de la máquina, y validar la tasa de falsos positivos.
7. **Eliminar `src/demo/`** y mover lo que sirva a la capa definitiva, dejando el wiring apuntando a las implementaciones productivas.

## TECHSTACK

- Visible en devenv.nix