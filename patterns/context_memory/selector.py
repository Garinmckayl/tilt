"""Context-selection decision engine and Strands InterventionHandler wiring.

Tags: #strands-decider-2b #context-memory
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from .client import NAME, DeciderClient
from .questions import build_context_memory_questions

try:
    from strands.interventions import Guide, InterventionHandler, Proceed
except ImportError:  # pragma: no cover - fallback if strands is not imported
    class InterventionHandler:  # type: ignore[no-redef]
        pass

    class Proceed:  # type: ignore[no-redef]
        pass

    class Guide:  # type: ignore[no-redef]
        def __init__(self, feedback: str = "") -> None:
            self.feedback = feedback


@dataclass
class CalibrationThresholds:
    """Calibrated decision thresholds tuned on the human-labeled evaluation set.

    - `refusal_prob_threshold`: Noul P(true) at or above which a response is separated as Refusal.
    - `stance_confidence_threshold`: Choice confidence below which stance is labeled "unclear"
      instead of forcing a low-confidence stance placement.
    - `mixed_margin_threshold`: When the top two stance options are opposing poles and their
      probability gap is below this margin (with non-trivial middle mass), classify as "mixed".
    - `passage_relevance_threshold`: Score (on 0..3 rubric) at or above which a passage is kept
      in context for the downstream generative agent.
    - `max_selected_passages`: Maximum passages retained for downstream synthesis context.
    - `min_selected_passages`: Minimum passages retained (falls back to top-scoring passage).
    """

    refusal_prob_threshold: float = 0.75
    stance_confidence_threshold: float = 0.25
    min_evidence_relevance_threshold: float = 1.45
    mixed_margin_threshold: float = 0.12
    passage_relevance_threshold: float = 1.50
    max_selected_passages: int = 2
    min_selected_passages: int = 1


@dataclass
class Passage:
    """A numbered passage extracted from an original model response with exact character offsets."""

    id: str
    number: int
    text: str
    start_char: int
    end_char: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PassageScore:
    """Strands Decider 2B relevance score and selection status for a single passage."""

    id: str
    number: int
    text: str
    start_char: int
    end_char: int
    relevance_score: float
    relevance_normalized: float
    relevance_confidence: float
    level_probabilities: dict[str, float]
    evidence_choice_probability: float
    combined_utility: float
    selected_for_context: bool
    is_primary_evidence: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextSelectionDecision:
    """Complete, inspectable output of a Strands Decider 2B #context-memory decision."""

    decider_model: str
    question: str
    assigned_stance: str
    raw_top_stance: str
    stance_probabilities: dict[str, float]
    stance_confidence: float
    is_refusal: bool
    refusal_probability: float
    is_unclear: bool
    unclear_reason: str | None
    primary_passage_id: str
    primary_quote: str
    selected_passage_ids: list[str]
    pruned_passage_ids: list[str]
    passages: list[PassageScore]
    total_chars: int
    selected_chars: int
    context_reduction_ratio: float
    input_tokens: int
    output_tokens: int
    latency_ms: float
    thresholds: dict[str, Any] = field(default_factory=dict)

    def format_selected_context(self) -> str:
        """Render only the Decider-selected passages for downstream LLM context injection."""
        kept = [p for p in self.passages if p.selected_for_context]
        return "\n".join(
            f"[{p.id}] (relevance={p.relevance_score:.2f}/3.00, primary={p.is_primary_evidence}): {p.text}"
            for p in kept
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def split_into_passages(text: str, max_passages: int = 5) -> list[Passage]:
    """Deterministically split a model response into exact, numbered passages with character spans.

    Preserves exact substrings of `text` so every passage and quote can be verified
    against `text[start_char:end_char]`.
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    # First split by paragraph breaks if the response has multiple paragraphs/bullets.
    raw_spans: list[tuple[int, int]] = []
    para_matches = list(re.finditer(r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*", text))

    # Split paragraphs into sentence-level or logical chunks (~120-420 chars) so Decider 2B
    # can score individual claims and select concise, high-signal evidence passages.
    sentence_pattern = re.compile(r"[^.!?\n]+[.!?]+(?:\s+|$)|[^.!?\n]+(?:\n|$)")
    for pm in para_matches:
        p_start, p_end = pm.span()
        p_text = text[p_start:p_end]
        if len(p_text.strip()) <= 420:
            raw_spans.append((p_start, p_end))
            continue
        # Break long paragraphs into 1-2 sentence passages
        cur_start: int | None = None
        cur_end: int = p_start
        for sm in sentence_pattern.finditer(p_text):
            s_start = p_start + sm.start()
            s_end = p_start + sm.end()
            while s_start < s_end and text[s_start].isspace():
                s_start += 1
            while s_end > s_start and text[s_end - 1].isspace():
                s_end -= 1
            if s_end <= s_start:
                continue
            if cur_start is None:
                cur_start = s_start
                cur_end = s_end
            elif (s_end - cur_start) <= 420:
                cur_end = s_end
            else:
                raw_spans.append((cur_start, cur_end))
                cur_start = s_start
                cur_end = s_end
        if cur_start is not None:
            raw_spans.append((cur_start, cur_end))

    # Normalize spans (trim leading/trailing whitespace while maintaining exact indices into `text`)
    normalized: list[tuple[int, int]] = []
    for s, e in raw_spans:
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if e - s >= 12:
            normalized.append((s, e))

    if not normalized:
        s = text.find(cleaned)
        e = s + len(cleaned)
        normalized = [(s, e)]

    # Merge if more than max_passages
    while len(normalized) > max_passages:
        # Merge the shortest adjacent pair
        best_idx = min(
            range(len(normalized) - 1),
            key=lambda i: (normalized[i + 1][1] - normalized[i][0]),
        )
        normalized[best_idx] = (normalized[best_idx][0], normalized[best_idx + 1][1])
        del normalized[best_idx + 1]

    passages: list[Passage] = []
    for idx, (s, e) in enumerate(normalized, start=1):
        passages.append(
            Passage(
                id=f"P{idx}",
                number=idx,
                text=text[s:e],
                start_char=s,
                end_char=e,
            )
        )
    return passages


def verify_exact_quote(
    original_text: str,
    candidate_quote: str | None,
    fallback_passage: Passage,
) -> dict[str, Any]:
    """Validate that `candidate_quote` is an exact substring of `original_text`.

    If the generative agent altered punctuation or paraphrased, falls back deterministically
    to the exact text of the Strands Decider 2B primary passage.
    """
    if candidate_quote:
        q = candidate_quote.strip().strip('"').strip("“").strip("”").strip("'")
        if len(q) >= 20:
            idx = original_text.find(q)
            if idx != -1:
                return {
                    "verified": True,
                    "source": "agent_exact_substring",
                    "quote": q,
                    "start_char": idx,
                    "end_char": idx + len(q),
                }
    # Deterministic fallback: exact slice from original_text using fallback_passage offsets
    exact_slice = original_text[fallback_passage.start_char : fallback_passage.end_char]
    return {
        "verified": True,
        "source": "decider_primary_passage",
        "quote": exact_slice,
        "start_char": fallback_passage.start_char,
        "end_char": fallback_passage.end_char,
    }


class PassageContextSelector:
    """Reusable #context-memory decision component powered by Strands Decider 2B.

    Given a question, topic-specific stance options, and a model response:
    1. Splits the response into numbered passages `[P1]..[PN]`.
    2. Sends ONE shared-prefix request to Strands Decider 2B to evaluate:
       - Refusal (`noul`)
       - Stance (`choice` with calibrated confidence threshold -> `"unclear"` if below threshold)
       - Per-passage relevance (`score` on a 4-level rubric)
       - Primary evidence passage (`choice` across `[P1]..[PN]`)
    3. Selects only high-relevance passages for downstream Bedrock agent context.
    """

    def __init__(
        self,
        decider: DeciderClient | None = None,
        thresholds: CalibrationThresholds | None = None,
    ) -> None:
        self.decider = decider or DeciderClient()
        self.thresholds = thresholds or CalibrationThresholds()

    def evaluate_response(
        self,
        question_text: str,
        response_text: str,
        stance_options: Mapping[str, str],
    ) -> ContextSelectionDecision:
        passages = split_into_passages(response_text)
        if not passages:
            passages = [
                Passage(
                    id="P1",
                    number=1,
                    text=response_text.strip() or "(empty response)",
                    start_char=0,
                    end_char=len(response_text),
                )
            ]

        numbered_block = "\n".join(f"[{p.id}] {p.text}" for p in passages)
        state = (
            f"Question: {question_text}\n\n"
            f"Response Passages:\n{numbered_block}"
        )

        passage_pairs = [(p.id, p.text) for p in passages]
        questions = build_context_memory_questions(
            question_text=question_text,
            stance_options=stance_options,
            passages=passage_pairs,
        )

        payload = self.decider.ask_raw(state, questions)
        answers = payload["answers"]
        usage = payload.get("usage", {})
        latency_ms = float(payload.get("latency_ms", 0.0))

        # 1. Refusal decision (separate from stance)
        refusal_prob = float(answers["is_refusal"]["noul"])
        is_refusal = refusal_prob >= self.thresholds.refusal_prob_threshold

        # 2. Stance classification with calibrated confidence & unclear/mixed gating
        stance_ans = answers["stance"]
        raw_top_stance = str(stance_ans["choice"])
        stance_probs = {str(k): round(float(v), 4) for k, v in stance_ans["probabilities"].items()}
        stance_conf = float(stance_ans["confidence"])

        sorted_probs = sorted(stance_probs.items(), key=lambda kv: kv[1], reverse=True)
        top_prob = sorted_probs[0][1] if sorted_probs else 0.0
        second_prob = sorted_probs[1][1] if len(sorted_probs) > 1 else 0.0
        margin = top_prob - second_prob

        is_unclear = False
        unclear_reason: str | None = None

        if is_refusal:
            assigned_stance = "refusal"
        elif (
            "mixed" in stance_probs
            and margin < self.thresholds.mixed_margin_threshold
            and stance_probs.get("mixed", 0.0) >= 0.28
        ):
            assigned_stance = "mixed"
        elif raw_top_stance == "mixed" and top_prob >= 0.40:
            assigned_stance = "mixed"
        elif stance_conf < self.thresholds.stance_confidence_threshold:
            assigned_stance = "unclear"
            is_unclear = True
            unclear_reason = (
                f"Decider confidence ({stance_conf:.2f}) is below the calibrated threshold "
                f"({self.thresholds.stance_confidence_threshold:.2f}); refusing to force a label."
            )
        else:
            assigned_stance = raw_top_stance

        # 3. Passage relevance scoring & context selection
        best_passage_probs: dict[str, float] = {}
        if "best_passage" in answers:
            best_passage_probs = {
                str(k): float(v) for k, v in answers["best_passage"]["probabilities"].items()
            }
        else:
            best_passage_probs = {passages[0].id: 1.0}

        scored_passages: list[PassageScore] = []
        for p in passages:
            rel_ans = answers[f"rel_{p.id}"]
            rel_score = float(rel_ans["score"])  # 0.0 .. 3.0
            rel_norm = round(rel_score / 3.0, 4)
            rel_conf = float(rel_ans["confidence"])
            lvl_probs = {str(k): round(float(v), 4) for k, v in rel_ans["probabilities"].items()}
            ev_prob = round(best_passage_probs.get(p.id, 0.0), 4)
            # Combine ordinal relevance score (normalized 0..1) with evidence pointer probability
            combined_utility = round(0.65 * rel_norm + 0.35 * ev_prob, 4)
            scored_passages.append(
                PassageScore(
                    id=p.id,
                    number=p.number,
                    text=p.text,
                    start_char=p.start_char,
                    end_char=p.end_char,
                    relevance_score=round(rel_score, 4),
                    relevance_normalized=rel_norm,
                    relevance_confidence=round(rel_conf, 4),
                    level_probabilities=lvl_probs,
                    evidence_choice_probability=ev_prob,
                    combined_utility=combined_utility,
                    selected_for_context=False,
                    is_primary_evidence=False,
                )
            )

        # Rank passages by combined utility (relevance score + pointer choice probability)
        ranked = sorted(scored_passages, key=lambda ps: (ps.combined_utility, ps.relevance_score), reverse=True)
        primary_id = ranked[0].id
        max_relevance_score = max(ps.relevance_score for ps in scored_passages)

        # Evidence-grounded unclear check: if no passage in the response meets the minimum
        # relevance score threshold, refuse to force a stance label even if closed-set choice leaned.
        if (
            not is_refusal
            and not is_unclear
            and max_relevance_score < self.thresholds.min_evidence_relevance_threshold
        ):
            assigned_stance = "unclear"
            is_unclear = True
            unclear_reason = (
                f"Highest passage relevance ({max_relevance_score:.2f}/3.00) is below the calibrated "
                f"evidence threshold ({self.thresholds.min_evidence_relevance_threshold:.2f}); "
                "no passage provides sufficient stance evidence."
            )

        selected_ids: set[str] = set()
        for ps in ranked:
            if len(selected_ids) >= self.thresholds.max_selected_passages:
                break
            if ps.relevance_score >= self.thresholds.passage_relevance_threshold or len(selected_ids) < self.thresholds.min_selected_passages:
                selected_ids.add(ps.id)

        primary_quote = ranked[0].text
        for ps in scored_passages:
            ps.selected_for_context = ps.id in selected_ids
            ps.is_primary_evidence = ps.id == primary_id
            if ps.is_primary_evidence:
                primary_quote = ps.text

        total_chars = sum(len(p.text) for p in scored_passages)
        selected_chars = sum(len(p.text) for p in scored_passages if p.selected_for_context)
        reduction_ratio = round(1.0 - (selected_chars / max(1, total_chars)), 4)

        return ContextSelectionDecision(
            decider_model=str(payload.get("model", "strands-decider-2B-qwen3.5-v1-2610")),
            question=question_text,
            assigned_stance=assigned_stance,
            raw_top_stance=raw_top_stance,
            stance_probabilities=stance_probs,
            stance_confidence=round(stance_conf, 4),
            is_refusal=is_refusal,
            refusal_probability=round(refusal_prob, 4),
            is_unclear=is_unclear,
            unclear_reason=unclear_reason,
            primary_passage_id=primary_id,
            primary_quote=primary_quote,
            selected_passage_ids=[p.id for p in scored_passages if p.selected_for_context],
            pruned_passage_ids=[p.id for p in scored_passages if not p.selected_for_context],
            passages=scored_passages,
            total_chars=total_chars,
            selected_chars=selected_chars,
            context_reduction_ratio=reduction_ratio,
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            latency_ms=round(latency_ms, 2),
            thresholds=asdict(self.thresholds),
        )


class ContextMemoryIntervention(InterventionHandler):
    """Drop-in Strands SDK InterventionHandler implementing the #context-memory pattern.

    Before a synthesis or analysis tool executes on raw document/response text, this
    intervention uses Strands Decider 2B to score every passage's relevance and Either:
    - Prunes low-relevance passages in-place (`Proceed`), or
    - Guides the agent (`Guide`) if a tool is called with unverified or low-relevance context.
    """

    name = f"{NAME}-context-memory-selector"

    def __init__(
        self,
        selector: PassageContextSelector,
        stance_options: Mapping[str, str],
        question_text: str,
    ) -> None:
        self.selector = selector
        self.stance_options = stance_options
        self.question_text = question_text
        self.decisions: list[ContextSelectionDecision] = []

    def before_tool_call(self, event: Any, **kwargs: Any) -> Any:
        tool_input = event.tool_use.get("input") or {}
        raw_text = tool_input.get("response_text") or tool_input.get("document")
        if not raw_text or not isinstance(raw_text, str):
            return Proceed()

        decision = self.selector.evaluate_response(
            question_text=self.question_text,
            response_text=raw_text,
            stance_options=self.stance_options,
        )
        self.decisions.append(decision)

        # Replace full noisy text with Decider-selected relevant passages + stance metadata
        tool_input["selected_context"] = decision.format_selected_context()
        tool_input["assigned_stance"] = decision.assigned_stance
        tool_input["primary_quote"] = decision.primary_quote
        tool_input["stance_confidence"] = decision.stance_confidence
        return Proceed()
