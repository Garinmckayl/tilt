"""Zero-dependency HTTP client for a persistent Strands Decider 2B server.

Tags: #strands-decider-2b #context-memory
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

NAME = "strands-decider"
ENV_URL = "STRANDS_DECIDER_URL"
SERVE_HINT = "strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8099"
MODEL_ID = "strands-decider-2B-qwen3.5-v1-2610"
DEFAULT_PORT = 8099
DEFAULT_URL = os.environ.get(ENV_URL, f"http://127.0.0.1:{DEFAULT_PORT}")


class ServerUnavailable(RuntimeError):
    """Raised when the Strands Decider 2B server is unreachable."""


class DeciderClient:
    """One state, many typed questions, one round-trip over shared prefix KV cache."""

    def __init__(self, url: str = DEFAULT_URL, timeout: float = 120.0) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.last_latency_ms: float | None = None
        self.latencies_ms: list[float] = []

    @staticmethod
    def noul(instructions: str, criteria: Mapping[str, str] | None = None) -> dict[str, Any]:
        """Yes/no question returning P(true) in [0, 1]."""
        question: dict[str, Any] = {"type": "noul", "instructions": instructions}
        if criteria:
            question["criteria"] = dict(criteria)
        return question

    @staticmethod
    def choice(instructions: str, criteria: Mapping[str, str]) -> dict[str, Any]:
        """Closed-set choice question returning argmax, probabilities, and calibrated confidence."""
        return {"type": "choice", "instructions": instructions, "criteria": dict(criteria)}

    @staticmethod
    def score(instructions: str, criteria: list[str]) -> dict[str, Any]:
        """Ordinal rubric question returning expected value, level distribution, and confidence."""
        return {"type": "score", "instructions": instructions, "criteria": list(criteria)}

    def _unavailable(self, exc: Exception) -> ServerUnavailable:
        return ServerUnavailable(
            f"No {NAME} server responding at {self.url} ({exc}). Start one with:\n    {SERVE_HINT}"
        )

    def ask_raw(self, state: Any, questions: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
        """Evaluate `state` against `questions` and return the full SystemOne response payload."""
        body = json.dumps(
            {"state": state, "model": MODEL_ID, "questions": dict(questions)}
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.url}/v1/systemone",
            data=body,
            headers={"content-type": "application/json"},
        )
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise self._unavailable(exc) from exc
        wall_ms = round((time.perf_counter() - t0) * 1000, 2)
        server_ms = payload.get("latency_ms", wall_ms)
        self.calls += 1
        self.input_tokens += payload.get("usage", {}).get("input_tokens", 0)
        self.output_tokens += payload.get("usage", {}).get("output_tokens", 0)
        self.last_latency_ms = float(server_ms)
        self.latencies_ms.append(float(server_ms))
        payload["client_wall_ms"] = wall_ms
        return payload

    def ask(self, state: Any, questions: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
        """Evaluate `state` against `questions` and return the `answers` dictionary."""
        return self.ask_raw(state, questions)["answers"]

    def health(self) -> dict[str, Any]:
        """Return health and loaded checkpoint metadata from the Decider 2B server."""
        for path in ("/health/extended", "/health"):
            try:
                with urllib.request.urlopen(f"{self.url}{path}", timeout=5) as response:
                    return json.loads(response.read().decode("utf-8"))
            except Exception:
                continue
        raise self._unavailable(RuntimeError("health check failed"))
