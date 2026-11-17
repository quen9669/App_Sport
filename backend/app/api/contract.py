"""The common contract of every app of the portfolio (référentiel R-16, écart SPT-06).

- ``GET /health``: the app's state in the common format (● en_service,
  ◆ degrade, ■ arrete), read by the server's supervision (blackbox on the
  ``obs-net`` network). The app never sends alerts itself (R-26): it only
  turns this answer to ■, and the supervision does the rest.
- ``GET /vitrine.json``: key figures for the portfolio, aggregates only, never
  health data.

Both live at the root (not under /api) and need no sign-in: the supervision has
no session, and nothing here is personal. They reuse the Monitoring page's
checks (services/monitoring.py) instead of computing anything new.
"""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import Activity
from app.db.session import get_db
from app.repositories.activities import not_duplicate
from app.services.goals import streak, weeks_history
from app.services.monitoring import Status, monitoring
from app.services.weeks import current_week

router = APIRouter(tags=["contract"])

APP = "app-sport"
CODE = "EXP-04"
LINE = "ml"  # dominant line: MLOps, continuous self-improvement
# Kept in step with expedition.yaml (étape 5 sur 6).
STEP = 5
STEP_LABEL = "En production privée"
VERSION = "0.1.0"

State = Literal["en_service", "degrade", "arrete"]
# The Monitoring statuses in the common words. "unknown" (nothing to check yet,
# e.g. the coach without a key) never raises an alarm, as on the Monitoring page.
# A late sync is "degrade", not "arrete": the app still answers with the data it
# has. ■ arrete is kept for an app that cannot read its own database.
STATES: dict[Status, State] = {
    "ok": "en_service",
    "unknown": "en_service",
    "warning": "degrade",
    "error": "degrade",
}


class Check(BaseModel):
    nom: str
    etat: State
    detail: str | None = None


class HealthOut(BaseModel):
    app: str
    code: str
    etat: State
    version: str
    verifie_le: datetime
    controles: list[Check]


class Figure(BaseModel):
    libelle: str
    valeur: int


class VitrineOut(BaseModel):
    app: str
    code: str
    ligne: str
    etape: int
    etape_libelle: str
    chiffres: list[Figure]
    maj: datetime


@router.get("/health", response_model=HealthOut)
def read_health(
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthOut:
    now = datetime.now(UTC)
    try:
        data = monitoring(db, settings, now)
    except Exception:
        # The database cannot be read: the app is stopped for the supervision.
        # 503 lets a blackbox probe see ■ without reading the body.
        response.status_code = 503
        return HealthOut(
            app=APP,
            code=CODE,
            etat="arrete",
            version=VERSION,
            verifie_le=now,
            controles=[Check(nom="base", etat="arrete", detail="base illisible")],
        )
    checks = [Check(nom="base", etat="en_service")]
    for source in data.sources:
        detail = source.last_error if source.status != "ok" else None
        checks.append(
            Check(nom=f"synchro_{source.source}", etat=STATES[source.status], detail=detail)
        )
    checks.append(Check(nom="coach", etat=STATES[data.coach.status]))
    checks.append(Check(nom="memoire", etat=STATES[data.memory.status]))
    return HealthOut(
        app=APP,
        code=CODE,
        etat=STATES[data.status],
        version=VERSION,
        verifie_le=now,
        controles=checks,
    )


@router.get("/vitrine.json", response_model=VitrineOut)
def read_vitrine(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> VitrineOut:
    sessions = db.scalar(
        select(func.count())
        .select_from(Activity)
        .where(not_duplicate(), Activity.hidden.is_(False))
    )
    current = current_week(settings.app_timezone)
    history = weeks_history(db, current, 52, settings.app_timezone)
    return VitrineOut(
        app=APP,
        code=CODE,
        ligne=LINE,
        etape=STEP,
        etape_libelle=STEP_LABEL,
        chiffres=[
            Figure(libelle="Séances synchronisées", valeur=int(sessions or 0)),
            Figure(
                libelle="Semaines d'objectifs réussies d'affilée", valeur=streak(history, current)
            ),
        ],
        maj=datetime.now(UTC),
    )
