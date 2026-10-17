"""Persistent comparison storage and rate-limiting for TILT.

Stores every comparison run on disk under `data/comparisons/` so that:
1. Curated questions load instantaneously with full provenance and a clear `cached: true` badge,
   while still allowing live re-runs when requested.
2. Every comparison (curated or custom) receives a permanent shareable ID (`/c/[id]`).
3. Public inference spending is bounded via a sliding-window token bucket rate limiter.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.environ.get("TILT_DATA_DIR", "/home/ubuntu/tilt/data"))
COMPARISONS_DIR = DATA_DIR / "comparisons"
TOPIC_INDEX_PATH = DATA_DIR / "curated_index.json"

_LOCK = threading.Lock()


def _ensure_dirs() -> None:
    COMPARISONS_DIR.mkdir(parents=True, exist_ok=True)


def normalize_question_key(question: str) -> str:
    cleaned = " ".join(question.strip().lower().split()).rstrip("?.!")
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:16]


def save_comparison(comparison: dict[str, Any], set_as_topic_default: bool = True) -> dict[str, Any]:
    """Persist a comparison result by its permanent ID and optionally update the topic index."""
    _ensure_dirs()
    comp_id = str(comparison["id"])
    file_path = COMPARISONS_DIR / f"{comp_id}.json"

    with _LOCK:
        file_path.write_text(json.dumps(comparison, indent=2, ensure_ascii=False))

        index_data = _load_index_unlocked()
        topic_id = comparison.get("topic", {}).get("id")
        q_key = normalize_question_key(str(comparison.get("question", "")))

        if set_as_topic_default and topic_id:
            index_data.setdefault("by_topic_id", {})[topic_id] = comp_id
        if q_key:
            index_data.setdefault("by_question_key", {})[q_key] = comp_id

        TOPIC_INDEX_PATH.write_text(json.dumps(index_data, indent=2, ensure_ascii=False))

    return comparison


def get_comparison_by_id(comp_id: str, mark_cached: bool = True) -> dict[str, Any] | None:
    """Retrieve a saved comparison by its permanent shareable ID (or topic ID prefix)."""
    _ensure_dirs()
    safe_id = "".join(c for c in comp_id if c.isalnum() or c in "-_")
    direct_path = COMPARISONS_DIR / f"{safe_id}.json"
    if direct_path.exists():
        data = json.loads(direct_path.read_text())
        if mark_cached:
            data = copy.deepcopy(data)
            data["cached"] = True
        return data

    # Also check if comp_id matches a curated topic_id
    by_topic = get_cached_for_topic(safe_id)
    if by_topic is not None:
        return by_topic
    return None


def get_cached_for_topic(topic_id: str) -> dict[str, Any] | None:
    """Return the canonical cached comparison for a curated topic_id, marked `cached: True`."""
    _ensure_dirs()
    with _LOCK:
        index_data = _load_index_unlocked()
    comp_id = index_data.get("by_topic_id", {}).get(topic_id)
    if not comp_id:
        return None
    return get_comparison_by_id(comp_id, mark_cached=True)


def get_cached_for_question(question: str) -> dict[str, Any] | None:
    """Return a cached comparison matching the normalized question string, if available."""
    _ensure_dirs()
    q_key = normalize_question_key(question)
    with _LOCK:
        index_data = _load_index_unlocked()
    comp_id = index_data.get("by_question_key", {}).get(q_key)
    if not comp_id:
        return None
    return get_comparison_by_id(comp_id, mark_cached=True)


def list_all_curated_comparisons() -> dict[str, dict[str, Any]]:
    """Return a map of `topic_id -> comparison` for all precomputed curated topics."""
    _ensure_dirs()
    with _LOCK:
        index_data = _load_index_unlocked()
    by_topic = index_data.get("by_topic_id", {})
    result: dict[str, dict[str, Any]] = {}
    for topic_id, comp_id in by_topic.items():
        comp = get_comparison_by_id(comp_id, mark_cached=True)
        if comp is not None:
            result[topic_id] = comp
    return result


def _load_index_unlocked() -> dict[str, Any]:
    if TOPIC_INDEX_PATH.exists():
        try:
            return json.loads(TOPIC_INDEX_PATH.read_text())
        except Exception:
            pass
    return {"by_topic_id": {}, "by_question_key": {}}


class InferenceBudgetGuard:
    """Sliding-window rate limiter to protect public Bedrock inference spending."""

    def __init__(self, max_live_runs_per_hour: int = 45, max_live_runs_per_ip_10m: int = 8) -> None:
        self.max_global_per_hour = max_live_runs_per_hour
        self.max_ip_per_10m = max_live_runs_per_ip_10m
        self._global_timestamps: list[float] = []
        self._ip_timestamps: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def check_and_record(self, client_ip: str) -> tuple[bool, str | None]:
        now = time.time()
        with self._lock:
            self._global_timestamps = [t for t in self._global_timestamps if now - t < 3600]
            ip_list = [t for t in self._ip_timestamps.get(client_ip, []) if now - t < 600]

            if len(self._global_timestamps) >= self.max_global_per_hour:
                return (
                    False,
                    "Hourly public live-inference budget reached. Cached comparisons remain available.",
                )
            if len(ip_list) >= self.max_ip_per_10m:
                return (
                    False,
                    "Rate limit reached for live custom comparisons (max 8 per 10 minutes). Try a curated topic or wait a few minutes.",
                )

            self._global_timestamps.append(now)
            ip_list.append(now)
            self._ip_timestamps[client_ip] = ip_list
            return True, None
