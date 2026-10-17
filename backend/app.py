"""FastAPI backend service for TILT: Ground News for AI.

Exposes:
- `GET /api/health`: Backend + persistent Strands Decider 2B health & hardware diagnostics
- `GET /api/topics`: All 8 curated topics across Technology, Culture, Economics, Politics
  with their topic-specific stance definitions and pre-loaded comparison summaries
- `GET /api/comparisons/{comparison_id}`: Fetch a specific comparison by permanent ID or topic ID
- `POST /api/compare`: Run or retrieve a 3-model comparison for a curated topic or custom question
- `GET /api/evaluation`: Return the human-labeled evaluation report, calibrated thresholds,
  and measured AWS deployment latency
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.pipeline import COMPARISON_MODELS, DECIDER_URL, run_comparison_pipeline
from backend.storage import (
    InferenceBudgetGuard,
    get_cached_for_question,
    get_cached_for_topic,
    get_comparison_by_id,
    list_all_curated_comparisons,
    save_comparison,
)
from backend.topics import CURATED_TOPICS, CURATED_TOPICS_BY_ID
from patterns.context_memory import DeciderClient

EVAL_RESULTS_PATH = Path("/home/ubuntu/tilt/evaluation/results.json")

app = FastAPI(
    title="TILT: Ground News for AI (Strands Decider 2B Backend)",
    version="1.0.0",
    description=(
        "Same question. Different AI. See the slant. "
        "Powered by Strands Agents, Strands Decider 2B (#strands-decider-2b), "
        "the reusable #context-memory passage-selection pattern, and Amazon Bedrock."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

budget_guard = InferenceBudgetGuard()


class CompareRequest(BaseModel):
    topic_id: str | None = Field(
        default=None,
        description="ID of one of the 8 curated questions (e.g. 'smartphones-in-schools').",
    )
    question: str | None = Field(
        default=None,
        description="Custom controversial question submitted by the user.",
    )
    custom_pole_a: str | None = Field(
        default=None,
        description="Optional custom left-pole stance label.",
    )
    custom_pole_b: str | None = Field(
        default=None,
        description="Optional custom right-pole stance label.",
    )
    force_live: bool = Field(
        default=False,
        description="If true, bypass cache and run a fresh live Bedrock + Strands Decider 2B comparison.",
    )


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    client = DeciderClient(url=DECIDER_URL, timeout=5.0)
    try:
        decider_health = client.health()
    except Exception as exc:
        decider_health = {"status": "unreachable", "error": str(exc)}

    curated_map = list_all_curated_comparisons()
    return {
        "status": "ok",
        "service": "tilt-backend",
        "pattern_tags": ["#strands-decider-2b", "#context-memory"],
        "decider_service": decider_health,
        "curated_topics_count": len(CURATED_TOPICS),
        "cached_curated_runs_count": len(curated_map),
        "models": [
            {
                "slot_id": m.slot_id,
                "display_name": m.display_name,
                "provider": m.provider,
                "bedrock_model_id": m.bedrock_model_id,
            }
            for m in COMPARISON_MODELS
        ],
    }


@app.get("/api/topics")
def api_topics() -> dict[str, Any]:
    curated_runs = list_all_curated_comparisons()
    topics_out: list[dict[str, Any]] = []
    for t in CURATED_TOPICS:
        td = t.to_dict()
        cached_run = curated_runs.get(t.id)
        if cached_run:
            td["comparison_id"] = cached_run["id"]
            td["created_at"] = cached_run["created_at"]
            td["summary"] = cached_run.get("summary", {})
            td["preview_placements"] = [
                {
                    "slot_id": m["slot_id"],
                    "display_name": m["display_name"],
                    "short_name": m["short_name"],
                    "family": m["family"],
                    "accent_color": m["accent_color"],
                    "bucket": m["placement"]["bucket"],
                    "stance_label": m["placement"]["stance_label"],
                    "stance_short_label": m["placement"]["stance_short_label"],
                    "on_spectrum": m["placement"]["on_spectrum"],
                    "spectrum_x": m["placement"]["spectrum_x"],
                }
                for m in cached_run.get("models", [])
            ]
        topics_out.append(td)

    return {
        "topics": topics_out,
        "comparisons_by_topic": curated_runs,
    }


@app.get("/api/comparisons/{comparison_id}")
def api_get_comparison(comparison_id: str) -> dict[str, Any]:
    comp = get_comparison_by_id(comparison_id, mark_cached=True)
    if comp is None:
        raise HTTPException(status_code=404, detail=f"Comparison '{comparison_id}' not found.")
    return comp


@app.post("/api/compare")
def api_compare(req: CompareRequest, request: Request) -> dict[str, Any]:
    # 1. Check cache unless force_live is True
    if not req.force_live:
        if req.topic_id and req.topic_id in CURATED_TOPICS_BY_ID:
            cached = get_cached_for_topic(req.topic_id)
            if cached is not None:
                return cached
        if req.question and req.question.strip():
            cached = get_cached_for_question(req.question.strip())
            if cached is not None:
                return cached

    # Validate question length
    if not req.topic_id and (not req.question or len(req.question.strip()) < 8):
        raise HTTPException(
            status_code=400,
            detail="Please enter a complete question (at least 8 characters) or select a curated topic.",
        )
    if req.question and len(req.question.strip()) > 260:
        raise HTTPException(
            status_code=400,
            detail="Please keep custom questions under 260 characters.",
        )

    # 2. Enforce public inference rate limit
    client_ip = request.client.host if request.client else "unknown"
    allowed, reason = budget_guard.check_and_record(client_ip)
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)

    # 3. Execute live 3-model comparison + Strands Decider 2B + Strands synthesis agent
    result = run_comparison_pipeline(
        topic_id=req.topic_id,
        custom_question=req.question,
        custom_pole_a=req.custom_pole_a,
        custom_pole_b=req.custom_pole_b,
    )
    save_comparison(
        result,
        set_as_topic_default=bool(req.topic_id and req.topic_id in CURATED_TOPICS_BY_ID),
    )
    return result


@app.get("/api/evaluation")
def api_evaluation() -> dict[str, Any]:
    if not EVAL_RESULTS_PATH.exists():
        raise HTTPException(status_code=404, detail="Evaluation results not found.")
    return json.loads(EVAL_RESULTS_PATH.read_text())
