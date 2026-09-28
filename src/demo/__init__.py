"""Implementaciones reales (no simuladas) para la DEMO con datos AEP.

Este paquete existe sólo para la demostración: reemplaza los mocks de `src/mocks`
por clases que cumplen las mismas interfaces de `src/domain`, pero que leen el
dataset real de AEP (Kaggle) y entrenan un modelo de scikit-learn.

Nada de lo que hay aquí es parte del sistema productivo: al conectar los datos
reales de la máquina de Plasticaucho se borra el paquete y se implementan las
mismas interfaces en la capa definitiva. Ver README > DEMO AEP.
"""

from __future__ import annotations
