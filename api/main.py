"""FastAPI app entrypoint for the regime-rader dashboard API.

API-first: the Next.js dashboard talks to this service for everything, no
static JSON files. Fully self-contained within regime-rader -- its
GarchXModel dependency is a local copy (models/garch_x_model.py, credited
to kb-balance in that module's own docstring, same pattern as
hrp_core.py), and ECOS_API_KEY comes from this repo's own .env. No path
into kb-balance is required to run this service.

Run from the repo root:
    .venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import backtest, hrp, regime

app = FastAPI(
    title="regime-rader API",
    description="Regime-conditional HRP allocation service -- regime detection, HRP history, and backtest results.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    # Dashboard's exact deploy origin isn't fixed yet; every route here is
    # read-only (GET) and serves no secrets, so an open origin list is
    # low-risk for now -- tighten to the real Next.js origin once it exists.
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(regime.router)
app.include_router(hrp.router)
app.include_router(backtest.router)


@app.get("/")
def root():
    return {"service": "regime-rader API", "status": "ok"}
