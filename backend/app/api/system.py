"""Служебные методы: здоровье, метрики, справочники и машина состояний для интерфейса."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app import __version__
from app.api.deps import DB
from app.domain.checklist import DOC_TYPES
from app.domain.decision.engine import COLLATERAL_TITLES, REASONS
from app.domain.okved import REGIONS, SECTORS
from app.domain.products import PURPOSES
from app.domain.scoring import load_scorecard
from app.domain.state_machine import TRANSITIONS
from app.domain.statuses import CLIENT_STAGES, STATUS_META
from app.integrations.client import SOURCE_TITLES, http_client

router = APIRouter(tags=["Служебные"])


@router.get("/api/health/live", summary="Процесс жив")
def live():
    return {"status": "ok", "version": __version__}


@router.get("/api/health/ready", summary="Готовность: БД и симулятор внешних систем")
def ready(db: DB):
    checks = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["database"] = f"error: {type(e).__name__}"
    try:
        r = http_client().get("/health", timeout=2.0)
        checks["integrations"] = "ok" if r.status_code == 200 else f"http {r.status_code}"
    except Exception as e:  # noqa: BLE001
        checks["integrations"] = f"degraded: {type(e).__name__}"
    # недоступность источников не делает API неготовым — конвейер деградирует в ручную проверку
    ok = checks["database"] == "ok"
    return JSONResponse({"status": "ok" if ok else "unavailable", "checks": checks, "version": __version__},
                        status_code=200 if ok else 503)


@router.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/api/v1/meta/state-machine", tags=["Справочники"], summary="Статусы, переходы и шаги маршрута")
def state_machine():
    return {
        "statuses": [{"code": s.value, "label": m.label, "client_label": m.client_label, "client_hint": m.client_hint,
                      "stage": m.stage, "waiting": m.waiting.value, "terminal": m.terminal, "sla_hours": m.sla_hours,
                      "tone": m.tone} for s, m in STATUS_META.items()],
        "transitions": [{"name": t.name, "from": sorted(s.value for s in t.sources), "to": t.target.value,
                         "actors": sorted(a.value for a in t.actors), "title": t.title} for t in TRANSITIONS],
        "client_stages": [{"key": k, "title": v} for k, v in CLIENT_STAGES],
    }


@router.get("/api/v1/meta/dictionaries", tags=["Справочники"], summary="Справочники для интерфейса")
def dictionaries():
    card = load_scorecard()
    return {
        "purposes": [{"code": k, **v} for k, v in PURPOSES.items()],
        "doc_types": [{"code": k, **v} for k, v in DOC_TYPES.items()],
        "collateral_types": [{"code": k, "title": v} for k, v in COLLATERAL_TITLES.items()],
        "decline_reasons": [{"code": k, "text": v["client"], "hint": v["hint"]} for k, v in REASONS.items()],
        "sources": [{"code": k, "title": v} for k, v in SOURCE_TITLES.items()],
        "sectors": [{"key": s.key, "name": s.name, "risk": s.risk, "gov_priority": s.gov_priority} for s in SECTORS.values()],
        "regions": [{"code": k, "name": v} for k, v in REGIONS.items()],
        "scorecard": {"model_id": card.model_id, "version": card.version, "grades": card.grades,
                      "features": [{"name": f["name"], "title": f["title"], "source": f["source"],
                                    "max_points": f["max_points"]} for f in card.spec["features"]]},
    }
