#!/usr/bin/env python
"""Entrena y evalúa el modelo de la demo AEP.

Uso (dentro del entorno devenv, con la venv activada):

    python scripts/train_aep_model.py
    python scripts/train_aep_model.py --holdout-days 60 --origins 100
    python scripts/train_aep_model.py --no-refit      # no reentrena con toda la serie

Qué hace:

1. Lee y limpia el dataset de Kaggle dentro de `data/kaggle-dataset.zip`.
2. Entrena un `HistGradientBoostingRegressor` con todo menos los últimos
   `--holdout-days` días.
3. Evalúa la TAREA REAL (desde un instante t, con las 72 h previas, predecir las
   8 h del turno siguiente) sobre ese holdout, con origenes repartidos.
4. Vuelve a entrenar sobre toda la serie y guarda el artefacto que consume el
   runtime (`artifacts/aep_model.joblib` + `artifacts/aep_metrics.json`).

Las métricas que se imprimen y se guardan corresponden al modelo que NO vio el
holdout; el artefacto final sí usa toda la serie, así que las métricas son una
estimación conservadora (pesimista) del desempeño real.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.demo.aep_training import run_training, save_artifact  # noqa: E402
from src.demo.aep_dataset import DEFAULT_ARTIFACT_DIR, DEFAULT_ZIP_PATH  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--zip", type=Path, default=DEFAULT_ZIP_PATH, help="ZIP con el CSV de AEP")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help="Directorio donde se guardan modelo y métricas",
    )
    parser.add_argument(
        "--holdout-days", type=int, default=90, help="Días finales reservados para evaluar"
    )
    parser.add_argument(
        "--origins", type=int, default=240, help="Cantidad de turnos evaluados en el backtest"
    )
    parser.add_argument(
        "--no-refit",
        action="store_true",
        help="No reentrenar con toda la serie (conserva el modelo evaluado)",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    args = parse_args()

    model, metrics, report = run_training(
        zip_path=args.zip,
        holdout_days=args.holdout_days,
        origins=args.origins,
        refit_on_full_series=not args.no_refit,
    )

    hourly = metrics["hourly"]
    total = metrics["shift_total"]
    print("\n=== Dataset ===")
    print(f"  filas crudas           : {report['raw_rows']}")
    print(f"  timestamps duplicados  : {report['duplicated_timestamps']}")
    print(f"  horas ausentes         : {report['missing_hours']}")
    print(f"  horas interpoladas     : {report['filled_hours']}")
    print(f"  serie final            : {report['clean_rows']} h  [{report['start']} → {report['end']}]")
    print(f"  filas de entrenamiento : {metrics['train_rows']}")

    print("\n=== Backtest (modelo sin ver el holdout) ===")
    print(f"  turnos evaluados       : {metrics['shifts_evaluated']}")
    print(f"  consumo horario        : MAE {hourly['mae']} · MAPE {hourly['mape']}% · RMSE {hourly['rmse']}")
    print(f"  total del turno        : MAE {total['mae']} · MAPE {total['mape']}%")
    print(f"  línea base (mediana horaria): {metrics['series_baseline_hourly_median']}")

    sigma = metrics["residual_sigma_by_hour"]
    print("\n=== σ residual por hora (base de las bandas de predicción) ===")
    print("  " + "  ".join(f"{hour}h:{value}" for hour, value in sorted(sigma.items(), key=lambda kv: int(kv[0]))))

    model_path, metrics_path = save_artifact(model, metrics, args.artifact_dir)
    print(f"\nArtefacto: {model_path}")
    print(f"Métricas : {metrics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
