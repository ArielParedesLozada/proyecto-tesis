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
├── devenv.nix / devenv.yaml      # Configuración de entorno de desarrollo reproducible (Nix/devenv).
└── requirements.txt              # Dependencias de Python (FastAPI, uvicorn, pydantic, etc.).
```

### Funcionalidad y Guía para LLMs y Extensiones
- **Punto Central de Wiring (`src/presentation/api/main.py`):** Los componentes de datos, predicción y límites se inyectan en `PredictionService`. Para conectar un modelo de IA real (ej. modelos basados en Machine Learning o Deep Learning) o una base de datos de históricos, solo se requiere implementar las interfaces del dominio (`EnergyDataSource`, `EnergyPredictionModel`, `ControlLimitCalculator`) y reemplazar las instancias correspondientes en el wiring de `main.py`, sin modificar la API ni el frontend.
- **Dominio Aislado (`src/domain/`):** Contiene el núcleo conceptual (modelos de datos inmutables y reglas operacionales independientes de frameworks externos), lo que permite a los LLMs razonar de manera precisa sobre la lógica de control energético y los estados operativos (`OPERATIVA`, `PARADA`, `MANTENIMIENTO`, `NORMAL`, `WARNING`, `ALERT`).

## TECHSTACK

- Visible en devenv.nix