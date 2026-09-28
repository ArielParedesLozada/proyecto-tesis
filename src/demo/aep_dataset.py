"""Carga, limpieza y feature engineering del dataset AEP para la DEMO.

Dataset de origen: "Unprocessed Energy Consumption Data (AEP)" (Kaggle), que
viene dentro de `data/kaggle-dataset.zip` con un único CSV:

    Datetime,AEP_MW
    12/31/2004 1:00,13478
    ...

Formato relevante (verificado sobre el archivo real):

- Fecha/hora en formato `M/D/YYYY H:MM`, **sin AM/PM ni cero a la izquierda**.
- 120 114 filas, 2004-10-01 00:00 → 2018-08-03 00:00, valores 9 581 – 25 164 MW.
- 0 nulos, 4 timestamps duplicados (caída de hora de verano) y 1 187 horas
  ausentes, siempre en rachas de 1 o 2 horas (interpolables sin inventar datos).

Unidades: la columna es potencia media horaria (MW). Como el intervalo es de
1 hora, el valor numérico coincide con la energía de esa hora; la demo lo
presenta tal cual (el frontend etiqueta "kWh") y lo documenta como limitación.

Este módulo es el ÚNICO lugar donde se toca pandas: el resto de la demo
consume DataFrames ya construidos, de modo que el modelo en runtime y el
script de entrenamiento comparten exactamente la misma ingeniería de variables.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ZIP_PATH = PROJECT_ROOT / "data" / "kaggle-dataset.zip"
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / "artifacts"
ARTIFACT_NAME = "aep_model.joblib"
METRICS_NAME = "aep_metrics.json"

#: Columna objetivo: energía horaria (numéricamente MW, ver docstring del módulo).
TARGET = "consumption"
#: Formato de fecha/hora del CSV de Kaggle.
DATETIME_FORMAT = "%m/%d/%Y %H:%M"
#: Longitud máxima (en horas) de los huecos que se interpolan. El dataset real
#: sólo tiene rachas de 1-2 h, así que este límite cubre el 100% de los huecos.
MAX_INTERPOLATED_GAP = 2
#: Horas de "calentamiento" que necesitan las variables de lags/medias móviles.
WARMUP_HOURS = 72
#: Horas usadas para las medias móvil / desviación de la inferencia.
SHORT_WINDOW = 6
LONG_WINDOW = 24
CONTEXT_WINDOW = 72

#: Variables categóricas que el HistGradientBoosting maneja de forma nativa.
CATEGORICAL_COLUMNS = ["hour", "dayofweek"]


def _read_csv_from_zip(zip_path: Path) -> pd.DataFrame:
    """Lee el primer CSV contenido en el ZIP del dataset."""
    with zipfile.ZipFile(zip_path) as archive:
        members = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if not members:
            raise FileNotFoundError(f"El ZIP {zip_path} no contiene ningún CSV")
        with archive.open(members[0]) as handle:
            raw = handle.read().decode("utf-8-sig")
    return pd.read_csv(io.StringIO(raw), dtype={"Datetime": "string", "AEP_MW": "float64"})


def load_raw_series(zip_path: Path | None = None) -> pd.Series:
    """Serie cruda (sin limpiar) indexada por timestamp, con duplicados."""
    zip_path = Path(zip_path) if zip_path else DEFAULT_ZIP_PATH
    if not zip_path.exists():
        raise FileNotFoundError(
            f"No se encontró el dataset AEP en {zip_path}. "
            "Descargá 'Unprocessed Energy Consumption Data (AEP)' de Kaggle y "
            "guardalo como data/kaggle-dataset.zip."
        )
    frame = _read_csv_from_zip(zip_path)
    timestamps = pd.to_datetime(frame["Datetime"], format=DATETIME_FORMAT, errors="coerce")
    values = pd.to_numeric(frame["AEP_MW"], errors="coerce")
    series = pd.Series(values.to_numpy(), index=pd.DatetimeIndex(timestamps), name=TARGET)
    return series[~series.index.isna()]


def clean_hourly_series(zip_path: Path | None = None) -> tuple[pd.Series, dict]:
    """Serie horaria continua: parseo, dedupe, orden, huecos interpolados.

    Devuelve la serie y un informe con los conteos del preprocesamiento
    (filas crudas, duplicados, horas rellenadas, rango final).
    """
    raw = load_raw_series(zip_path)
    report = {
        "raw_rows": int(raw.notna().sum()),
        "duplicated_timestamps": int(raw.index.duplicated().sum()),
    }

    # 1) Duplicados (caída de hora de verano): se conserva la primera lectura.
    series = raw[~raw.index.duplicated(keep="first")].sort_index()

    # 2) Serie horaria continua: se insertan las horas ausentes.
    index = pd.date_range(series.index.min(), series.index.max(), freq="h")
    series = series.reindex(index)
    report["missing_hours"] = int(series.isna().sum())

    # 3) Relleno de huecos cortos por interpolación temporal; los huecos más
    #    largos que el límite se dejan como NaN y se descartan más abajo.
    if MAX_INTERPOLATED_GAP > 0:
        series = series.interpolate(
            method="time", limit=MAX_INTERPOLATED_GAP, limit_direction="both"
        )
    series = series.dropna()
    report["filled_hours"] = report["missing_hours"] - int(series.isna().sum())
    report["clean_rows"] = int(series.size)
    report["start"] = series.index.min().isoformat()
    report["end"] = series.index.max().isoformat()
    series.name = TARGET
    return series, report


def proxy_temperature(ts: pd.Timestamp) -> float:
    """Temperatura ambiente sintética (°C) como proxy de "condición de máquina".

    El dataset AEP no tiene temperatura, así que se deriva del calendario con
    un ciclo diario + otro estacional. Es determinista: en runtime la misma
    función se aplica al timestamp de cada registro.
    """
    day_of_year = ts.dayofyear
    diurnal = 3.5 * np.sin(2 * np.pi * (ts.hour - 13) / 24)
    seasonal = 6.0 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
    return 24.0 + diurnal + seasonal


def proxy_operational(
    trailing_mean: float, baseline: float
) -> tuple[float, float]:
    """Proxies de "producción" (uds/h) y "carga" (%) a partir del nivel reciente.

    `trailing_mean` es la media de las 3 horas **previas** (información
    disponible en el momento de predecir) y `baseline` el nivel típico de esa
    hora del día. Nunca usa el valor que se quiere predecir, para no filtrar
    información del objetivo.
    """
    if baseline <= 0:
        baseline = 1.0
    ratio = trailing_mean / baseline
    production = float(np.clip(400.0 * ratio, 0.0, 900.0))
    load = float(np.clip(45.0 + 45.0 * ratio, 5.0, 100.0))
    return round(production, 1), round(load, 1)


def hourly_baseline(series: pd.Series) -> pd.Series:
    """Nivel típico de consumo por hora del día (mediana) de toda la serie."""
    return series.groupby(series.index.hour).median()


def build_feature_matrix(
    values: np.ndarray,
    timestamps: pd.DatetimeIndex,
    *,
    conditions: tuple[float, float, float] | None = None,
    hourly_reference: pd.Series | None = None,
) -> pd.DataFrame:
    """Matriz de variables para el modelo, en el mismo orden en todas partes.

    - Con `conditions=(temperatura, producción, carga)` las tres variables
      operacionales se fijan a ese valor para todas las filas. Es lo que hace
      el modelo en runtime: el turno a predecir hereda las condiciones
      actuales que entrega la fuente de datos.
    - Sin `conditions`, cada fila usa su propia temperatura de calendario y
      proxies calculados con las 3 horas previas (sin fuga de información).
    """
    values = np.asarray(values, dtype=float)
    index = pd.DatetimeIndex(timestamps)
    frame = pd.DataFrame(index=index)

    hour = index.hour.to_numpy()
    dayofweek = index.dayofweek.to_numpy()
    dayofyear = index.dayofyear.to_numpy()

    frame["hour"] = hour
    frame["dayofweek"] = dayofweek
    frame["is_weekend"] = (dayofweek >= 5).astype(float)
    frame["month"] = index.month.to_numpy()
    frame["year_index"] = (index.year.to_numpy() - index.year.min()).astype(float)

    # Armónicos del calendario: capturan la estacionalidad diaria/semanal/anual
    # sin exploding a hundreds de variables dummy.
    for k in (1, 2, 3):
        frame[f"hour_sin_{k}"] = np.sin(2 * np.pi * k * hour / 24)
        frame[f"hour_cos_{k}"] = np.cos(2 * np.pi * k * hour / 24)
    for k in (1, 2):
        frame[f"dow_sin_{k}"] = np.sin(2 * np.pi * k * dayofweek / 7)
        frame[f"dow_cos_{k}"] = np.cos(2 * np.pi * k * dayofweek / 7)
        frame[f"doy_sin_{k}"] = np.sin(2 * np.pi * k * dayofyear / 365)
        frame[f"doy_cos_{k}"] = np.cos(2 * np.pi * k * dayofyear / 365)

    # Lags y medias móviles: sólo información anterior al instante predecido.
    series = pd.Series(values, index=index)
    for lag in (1, 2, 3, 24, 48):
        frame[f"lag_{lag}"] = series.shift(lag).to_numpy()
    for window in (SHORT_WINDOW, LONG_WINDOW, CONTEXT_WINDOW):
        frame[f"roll_mean_{window}"] = (
            series.shift(1).rolling(window, min_periods=window).mean().to_numpy()
        )
    frame[f"roll_std_{LONG_WINDOW}"] = (
        series.shift(1).rolling(LONG_WINDOW, min_periods=LONG_WINDOW).std().to_numpy()
    )
    frame[f"roll_max_{LONG_WINDOW}"] = (
        series.shift(1).rolling(LONG_WINDOW, min_periods=LONG_WINDOW).max().to_numpy()
    )

    # Condiciones operacionales.
    if conditions is not None:
        temperature, production, load = conditions
        frame["temperature"] = float(temperature)
        frame["production"] = float(production)
        frame["load"] = float(load)
    else:
        frame["temperature"] = [proxy_temperature(ts) for ts in index]
        trailing = series.shift(1).rolling(3, min_periods=3).mean().to_numpy()
        if hourly_reference is not None:
            baseline = hourly_reference
        else:
            baseline = series.groupby(series.index.hour).median()
        fallback_trailing = float(np.nanmedian(trailing)) if trailing.size else 1.0
        fallback_baseline = float(baseline.median()) or 1.0
        proxies = [
            proxy_operational(
                fallback_trailing if np.isnan(value) else float(value),
                float(baseline.get(index[i].hour, fallback_baseline)),
            )
            for i, value in enumerate(trailing)
        ]
        frame["production"] = [p for p, _ in proxies]
        frame["load"] = [l for _, l in proxies]

    return frame


def feature_columns(frame: pd.DataFrame) -> list[str]:
    """Columnas de entrada del modelo (todo menos el objetivo)."""
    return [column for column in frame.columns if column != TARGET]


def supervised_frame(series: pd.Series) -> pd.DataFrame:
    """DataFrame listo para `fit`: variables + objetivo, sin filas incompletas.

    Se descartan las primeras `WARMUP_HOURS` horas (lags/medias sin historia) y
    cualquier fila con NaN, para que entrenamiento e inferencia sean idénticos.
    """
    reference = hourly_baseline(series)
    frame = build_feature_matrix(
        series.to_numpy(), series.index, hourly_reference=reference
    )
    frame[TARGET] = series.to_numpy()
    frame = frame.iloc[WARMUP_HOURS:]
    return frame.dropna()
