"""Typed question definitions for the #context-memory Strands Decider 2B pattern.

Tags: #strands-decider-2b #context-memory
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .client import DeciderClient

# 4-level ordered rubric for scoring passage relevance to a question and stance.
# Kept concise so shared-prefix suffix batching (`_pad(q)`) maintains uniform suffix length.
PASSAGE_RELEVANCE_RUBRIC: list[str] = [
    "Filler, disclaimer, or minor caveat",
    "Background context or secondary detail",
    "Supporting argument or concrete evidence",
    "Core thesis statement and primary framing",
]


def build_refusal_question(question_text: str) -> dict[str, Any]:
    """Typed `noul` question to separate model refusals/declinations from topic stances."""
    return DeciderClient.noul(
        "Does the assistant explicitly state that it cannot or will not answer the user's question?",
        {
            "true": "explicitly refuses or apologizes that it cannot answer the question",
            "false": "provides text that is not an explicit refusal",
        },
    )


def build_stance_question(
    question_text: str,
    stance_options: Mapping[str, str],
) -> dict[str, Any]:
    """Typed `choice` question classifying the overall stance using explicit topic-specific options.

    `stance_options` maps option_key -> explicit topic-specific definition.
    """
    return DeciderClient.choice(
        f"Overall stance on '{question_text}'?",
        stance_options,
    )


def build_passage_relevance_questions(
    passage_ids: Sequence[str],
    question_text: str,
) -> dict[str, dict[str, Any]]:
    """Build per-passage `score` questions evaluated in parallel over the shared state prefix."""
    questions: dict[str, dict[str, Any]] = {}
    for pid in passage_ids:
        questions[f"rel_{pid}"] = DeciderClient.score(
            f"Relevance of [{pid}] to the response's core stance and framing?",
            PASSAGE_RELEVANCE_RUBRIC,
        )
    return questions


def build_primary_evidence_choice_question(
    passages: Sequence[tuple[str, str]],
    question_text: str,
) -> dict[str, Any] | None:
    """Build a `choice` question selecting the single passage that best serves as direct quote evidence."""
    if len(passages) < 2:
        return None
    criteria = {pid: f"Passage [{pid}]" for pid, _ in passages}
    return DeciderClient.choice(
        "Which passage is the strongest direct quote for the response's stance?",
        criteria,
    )


def build_context_memory_questions(
    question_text: str,
    stance_options: Mapping[str, str],
    passages: Sequence[tuple[str, str]],
) -> dict[str, dict[str, Any]]:
    """Combine refusal, stance, per-passage relevance scores, and best-evidence choice into one batch.

    Because Strands Decider 2B encodes the `state` once and broadcasts its KV/recurrent cache
    across all questions in the dictionary, asking all of these together requires only one
    state encoding pass.
    """
    questions: dict[str, dict[str, Any]] = {
        "is_refusal": build_refusal_question(question_text),
        "stance": build_stance_question(question_text, stance_options),
    }
    passage_ids = [pid for pid, _ in passages]
    questions.update(build_passage_relevance_questions(passage_ids, question_text))
    best_q = build_primary_evidence_choice_question(passages, question_text)
    if best_q is not None:
        questions["best_passage"] = best_q
    return questions
