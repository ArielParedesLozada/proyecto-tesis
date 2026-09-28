"""Entrenamiento, backtesting y persistencia del modelo de la demo AEP.

Este módulo concentra la lógica de ML para que la usen tanto el script de
entrenamiento (`scripts/train_aep_model.py`) como el modelo en runtime
(`src.demo.aep_prediction_model.AEPGradientBoostingModel`): el forecast
recursivo es exactamente el mismo código en entrenamiento y en producción, que
es lo que hace que las métricas del backtest sean representativas.

Modelo: `HistGradientBoostingRegressor` de scikit-learn con variables de
calendario (hora, día de la semana, estación), lags, medias móviles y las
condiciones operacionales. Es un modelo de regresión ligero, entrenable en
segundos sobre ~120 k horas y sin GPU.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from joblib import dump, load
from sklearn.ensemble import HistGradientBoostingRegressor

from src.demo.aep_dataset import (
    ARTIFACT_NAME,
    CATEGORICAL_COLUMNS,
    DEFAULT_ARTIFACT_DIR,
    DEFAULT_ZIP_PATH,
    METRICS_NAME,
    TARGET,
    WARMUP_HOURS,
    build_feature_matrix,
    clean_hourly_series,
    feature_columns,
    hourly_baseline,
    supervised_frame,
)
from src.domain.shifts import SHIFT_HOURS, next_shift_start

LOGGER = logging.getLogger("demo.aep.training")
ARTIFACT_VERSION = 1


def fit_model(frame: pd.DataFrame) -> HistGradientBoostingRegressor:
    """Entrena el modelo sobre un DataFrame con variables + `TARGET`.

    Se pasan DataFrames (y no arrays) a propósito: así scikit-learn registra
    los nombres de las variables y `categorical_features` puede referenciarlas
    por nombre, además de validar el orden en cada `predict`.
    """
    columns = feature_columns(frame)
    model = HistGradientBoostingRegressor(
        categorical_features=CATEGORICAL_COLUMNS,
        max_iter=400,
        learning_rate=0.06,
        min_samples_leaf=40,
        l2_regularization=1.0,
        early_stopping=True,
        validation_fraction=0.1,
        random_state=42,
    )
    model.fit(frame[columns], frame[TARGET])
    return model


def recursive_forecast(
    model: Any,
    context_values: list[float],
    context_timestamps: list[datetime],
    conditions: tuple[float, float, float],
    start: datetime,
    steps: int = SHIFT_HOURS,
) -> list[float]:
    """Predice `steps` horas desde `start` de forma recursiva.

    En cada paso usa la misma ingeniería de variables que el entrenamiento
    (`build_feature_matrix`), alimentando el histórico con la predicción del
    paso anterior para los lags. La fila objetivo nunca ve su propio valor
    (todas las variables van desplazadas), por eso el placeholder `0.0` es
    irrelevante.
    """
    values = [float(v) for v in context_values]
    index = [pd.Timestamp(ts) for ts in context_timestamps]

    forecast: list[float] = []
    for step in range(steps):
        ts = pd.Timestamp(start) + pd.Timedelta(hours=step)
        values.append(0.0)
        index.append(ts)
        frame = build_feature_matrix(
            np.asarray(values), pd.DatetimeIndex(index), conditions=conditions
        )
        row = frame.iloc[[-1]].drop(columns=[TARGET], errors="ignore")
        prediction = float(model.predict(row)[0])
        prediction = max(0.0, prediction)
        values[-1] = prediction
        forecast.append(prediction)
    return forecast


def backtest(
    model: Any,
    series: pd.Series,
    features: pd.DataFrame,
    *,
    start: pd.Timestamp,
    origins: int,
) -> dict:
    """Evalúa el modelo replicando la tarea real: desde un instante `t`, con
    las 72 h previas, predecir las 8 h del turno siguiente y compararlas con
    la realidad.

    Devuelve métricas globales, por hora del día y la desviación residual por
    hora (base de las bandas de control de la predicción).
    """
    values = series.to_numpy()
    index = series.index
    baseline = hourly_baseline(series)

    first_position = int(series.index.searchsorted(start, side="left"))
    candidates = list(range(first_position, len(values) - SHIFT_HOURS))
    if not candidates:
        raise ValueError("No hay datos suficientes para el backtest solicitado")
    step = max(1, len(candidates) // origins)
    selected = candidates[::step][:origins]

    abs_errors: list[float] = []
    pct_errors: list[float] = []
    squared_errors: list[float] = []
    shift_abs_errors: list[float] = []
    shift_pct_errors: list[float] = []
    by_hour: dict[int, list[float]] = {hour: [] for hour in range(24)}
    by_shift_hour: dict[int, list[float]] = {hour: [] for hour in range(24)}
    evaluated = 0

    for position in selected:
        ts = index[position]
        shift_start = next_shift_start(ts.to_pydatetime())
        context_start = max(0, position - 72 + 1)
        context_values = values[context_start : position + 1]
        context_index = index[context_start : position + 1]
        if len(context_values) < WARMUP_HOURS:
            continue
        row = features.loc[ts]
        conditions = (
            float(row["temperature"]),
            float(row["production"]),
            float(row["load"]),
        )
        forecast = recursive_forecast(
            model,
            [float(v) for v in context_values],
            list(context_index),
            conditions,
            shift_start,
        )
        actuals = []
        valid = True
        for step, predicted in enumerate(forecast):
            target_ts = shift_start + timedelta(hours=step)
            position_target = index.get_indexer([pd.Timestamp(target_ts)])[0]
            if position_target < 0:
                valid = False
                break
            actual = float(values[position_target])
            actuals.append(actual)
            error = abs(actual - predicted)
            abs_errors.append(error)
            pct_errors.append(100.0 * error / actual if actual else 0.0)
            squared_errors.append((actual - predicted) ** 2)
            by_hour[target_ts.hour].append(actual - predicted)
            by_shift_hour[step].append(actual - predicted)
        if valid and actuals:
            total_error = abs(sum(actuals) - sum(forecast))
            total_actual = sum(actuals)
            shift_abs_errors.append(total_error)
            if total_actual:
                shift_pct_errors.append(100.0 * total_error / total_actual)
        evaluated += 1

    if not evaluated:
        raise ValueError("El backtest no evaluó ningún turno")

    def _summary(errors: list[float], pct: list[float], squares: list[float]) -> dict:
        return {
            "mae": round(float(np.mean(errors)), 2),
            "mape": round(float(np.mean(pct)), 3),
            "rmse": round(float(np.sqrt(np.mean(squares))), 2),
        }

    residual_sigma = {
        hour: round(float(np.std(residuals)), 2) for hour, residuals in by_hour.items() if residuals
    }
    residual_bias = {
        hour: round(float(np.mean(residuals)), 2) for hour, residuals in by_hour.items() if residuals
    }

    return {
        "shifts_evaluated": evaluated,
        "hourly": _summary(abs_errors, pct_errors, squared_errors),
        "shift_total": {
            "mae": round(float(np.mean(shift_abs_errors)), 2) if shift_abs_errors else 0.0,
            "mape": round(float(np.mean(shift_pct_errors)), 3) if shift_pct_errors else 0.0,
        },
        "by_hour_mape": {
            hour: round(100.0 * float(np.mean(np.abs(residuals))), 3)
            for hour, residuals in by_hour.items()
            if residuals
        },
        "residual_sigma_by_hour": residual_sigma,
        "residual_bias_by_hour": residual_bias,
        "residual_sigma_by_shift_hour": {
            step: round(float(np.std(residuals)), 2)
            for step, residuals in by_shift_hour.items()
            if residuals
        },
        "series_baseline_hourly_median": round(float(baseline.median()), 2),
    }


def run_training(
    zip_path: Path | None = None,
    holdout_days: int = 90,
    origins: int = 240,
    refit_on_full_series: bool = True,
) -> tuple[Any, dict, dict]:
    """Entrena y evalúa el modelo. Devuelve (modelo, métricas, reporte de datos)."""
    series, report = clean_hourly_series(zip_path)
    frame = supervised_frame(series)
    features = build_feature_matrix(
        series.to_numpy(), series.index, hourly_reference=hourly_baseline(series)
    )

    split = series.index[-1] - pd.Timedelta(days=holdout_days)
    train_frame = frame[frame.index <= split]
    if len(train_frame) < 10_000:
        raise ValueError("Datos insuficientes para entrenar con el holdout pedido")

    LOGGER.info(
        "Entrenando con %d filas (hasta %s); backtest sobre %d turnos (desde %s)",
        len(train_frame),
        train_frame.index[-1].date(),
        origins,
        split.date(),
    )
    model = fit_model(train_frame)
    metrics = backtest(model, series, features, start=split, origins=origins)
    metrics["holdout_days"] = holdout_days
    metrics["train_rows"] = int(len(train_frame))
    metrics["trained_until"] = str(train_frame.index[-1])
    metrics["model"] = type(model).__name__
    metrics["trained_at"] = datetime.now().isoformat(timespec="seconds")
    metrics["evaluated_without_holdout"] = True

    if refit_on_full_series:
        LOGGER.info("Reentrenando el artefacto final con toda la serie (%d filas)", len(frame))
        model = fit_model(frame)
        metrics["refit_on_full_series"] = True
    else:
        metrics["refit_on_full_series"] = False

    metrics["dataset"] = report
    return model, metrics, report


def save_artifact(
    model: Any,
    metrics: dict,
    artifact_dir: Path | None = None,
    columns: list[str] | None = None,
) -> tuple[Path, Path]:
    """Guarda el modelo (joblib) y las métricas (json) para el runtime."""
    artifact_dir = Path(artifact_dir) if artifact_dir else DEFAULT_ARTIFACT_DIR
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / ARTIFACT_NAME
    metrics_path = artifact_dir / METRICS_NAME

    dump(
        {
            "version": ARTIFACT_VERSION,
            "model": model,
            "columns": columns,
            "metrics": metrics,
        },
        model_path,
    )
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    return model_path, metrics_path


def load_artifact(artifact_path: Path | None = None) -> dict:
    """Carga el artefacto de entrenamiento. Lanza excepción si no existe o no
    es compatible (versión del modelo / versión de sklearn)."""
    artifact_path = Path(artifact_path) if artifact_path else DEFAULT_ARTIFACT_DIR / ARTIFACT_NAME
    if not artifact_path.exists():
        raise FileNotFoundError(
            f"No existe {artifact_path}. Generalo con: python scripts/train_aep_model.py"
        )
    payload = load(artifact_path)
    if payload.get("version") != ARTIFACT_VERSION:
        raise ValueError(
            f"Artefacto incompatible (versión {payload.get('version')} != {ARTIFACT_VERSION}); "
            "reentrená con scripts/train_aep_model.py"
        )
    return payload


__all__ = [
    "DEFAULT_ZIP_PATH",
    "backtest",
    "fit_model",
    "load_artifact",
    "recursive_forecast",
    "run_training",
    "save_artifact",
]
