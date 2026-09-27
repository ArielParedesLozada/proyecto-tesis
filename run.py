"""Punto de entrada local: arranca el servidor del mock.

Uso (dentro del entorno devenv):
    python run.py
    # o bien: uvicorn src.presentation.api.main:app
"""

from __future__ import annotations

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.presentation.api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )