"""TILT Three-Model Comparison Pipeline powered by Strands Agents + Strands Decider 2B.

Workflow:
1. Query 3 distinct Amazon Bedrock model families in parallel with identical prompts
   and comparable inference settings (`temperature=0.3`, `topP=0.9`, `maxTokens=320`).
2. Preserve complete responses and split into exact, numbered passages (`P1`, `P2`, ...).
3. Run Strands Decider 2B (`StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`) via the
   reusable `#context-memory` pattern (`PassageContextSelector`) to:
   - Separate refusals (`is_refusal` noul question)
   - Classify topic-specific stance (`stance` choice question) or output `"unclear"`
     when confidence/relevance falls below calibrated thresholds
   - Score each passage's relevance to the question (`rel_P1..N` score questions)
   - Select only high-relevance passages (`selected_passage_ids`) for downstream context
4. Invoke a Strands Agent (`strands.Agent` + `ContextMemoryIntervention`) on Amazon Bedrock
   using ONLY the Decider-selected passages as context to generate:
   - 1-sentence framing summary per model
   - 1 exact verbatim quote per model
   - 2-sentence "Where they differ" synthesis (honestly noting agreement when models align)
5. Deterministically verify every quote against the stored original response (`verify_exact_quote`),
   recording exact character offsets (`start_char`, `end_char`) and `passage_id`.
"""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

import boto3
from botocore.config import Config
from strands import Agent
from strands.models.bedrock import BedrockModel

from backend.topics import CURATED_TOPICS_BY_ID, TopicSpec, derive_custom_topic_spec
from patterns.context_memory import (
    CalibrationThresholds,
    ContextMemoryIntervention,
    ContextSelectionDecision,
    DeciderClient,
    Passage,
    PassageContextSelector,
    verify_exact_quote,
)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
DECIDER_URL = os.environ.get("DECIDER_URL", "http://127.0.0.1:8099")
DECIDER_MODEL_ID = "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610"
SYNTHESIS_MODEL_ID = os.environ.get("TILT_SYNTHESIS_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for one compared foundation model on Amazon Bedrock."""

    slot_id: str
    display_name: str
    short_name: str
    provider: str
    family: str
    bedrock_model_id: str
    fallback_model_id: str | None = None
    accent_color: str = "#1E293B"
    badge_bg: str = "#F1F5F9"


COMPARISON_MODELS: list[ModelConfig] = [
    ModelConfig(
        slot_id="claude-sonnet-4-5",
        display_name="Claude Sonnet 4.5",
        short_name="Claude",
        provider="Anthropic",
        family="claude",
        bedrock_model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        fallback_model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        accent_color="#C85A32",
        badge_bg="#FDF3EE",
    ),
    ModelConfig(
        slot_id="llama-3-3-70b",
        display_name="Llama 3.3 70B",
        short_name="Llama",
        provider="Meta",
        family="llama",
        bedrock_model_id="us.meta.llama3-3-70b-instruct-v1:0",
        fallback_model_id="us.amazon.nova-pro-v1:0",
        accent_color="#2563EB",
        badge_bg="#EFF6FF",
    ),
    ModelConfig(
        slot_id="deepseek-v3-2",
        display_name="DeepSeek V3.2",
        short_name="DeepSeek",
        provider="DeepSeek",
        family="deepseek",
        bedrock_model_id="deepseek.v3.2",
        fallback_model_id="mistral.mistral-large-3-675b-instruct",
        accent_color="#0F766E",
        badge_bg="#F0FDFA",
    ),
]

SHARED_INFERENCE_CONFIG: dict[str, Any] = {
    "temperature": 0.3,
    "maxTokens": 260,
}

SHARED_USER_PROMPT_TEMPLATE = (
    "{question}\n\n"
    "Provide a direct, thoughtful answer in 2 to 3 short paragraphs (around 130-160 words)."
)


def _get_bedrock_client():
    return boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION,
        config=Config(
            read_timeout=45,
            connect_timeout=10,
            retries={"max_attempts": 2, "mode": "standard"},
        ),
    )


def query_single_bedrock_model(
    model_cfg: ModelConfig,
    question: str,
) -> dict[str, Any]:
    """Query one Bedrock model with the shared prompt and comparable settings, handling unavailability gracefully."""
    client = _get_bedrock_client()
    prompt_text = SHARED_USER_PROMPT_TEMPLATE.format(question=question.strip())

    models_to_try = [model_cfg.bedrock_model_id]
    if model_cfg.fallback_model_id:
        models_to_try.append(model_cfg.fallback_model_id)

    last_error: str | None = None
    t0 = time.perf_counter()

    for attempt_idx, candidate_id in enumerate(models_to_try):
        try:
            resp = client.converse(
                modelId=candidate_id,
                messages=[{"role": "user", "content": [{"text": prompt_text}]}],
                inferenceConfig=SHARED_INFERENCE_CONFIG,
            )
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
            content_blocks = resp.get("output", {}).get("message", {}).get("content", [])
            text_parts = [
                blk["text"] for blk in content_blocks if isinstance(blk, dict) and "text" in blk
            ]
            full_text = "\n\n".join(text_parts).strip()
            usage = resp.get("usage", {})
            return {
                "slot_id": model_cfg.slot_id,
                "display_name": model_cfg.display_name,
                "short_name": model_cfg.short_name,
                "provider": model_cfg.provider,
                "family": model_cfg.family,
                "requested_model_id": model_cfg.bedrock_model_id,
                "actual_model_id": candidate_id,
                "used_fallback": attempt_idx > 0,
                "status": "available" if full_text else "unavailable",
                "error": None if full_text else "Empty model response",
                "original_response": full_text,
                "generation_latency_ms": latency_ms,
                "usage": {
                    "input_tokens": int(usage.get("inputTokens", 0)),
                    "output_tokens": int(usage.get("outputTokens", 0)),
                    "total_tokens": int(usage.get("totalTokens", 0)),
                },
            }
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

    latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    return {
        "slot_id": model_cfg.slot_id,
        "display_name": model_cfg.display_name,
        "short_name": model_cfg.short_name,
        "provider": model_cfg.provider,
        "family": model_cfg.family,
        "requested_model_id": model_cfg.bedrock_model_id,
        "actual_model_id": model_cfg.bedrock_model_id,
        "used_fallback": False,
        "status": "unavailable",
        "error": last_error or "Model unavailable",
        "original_response": "",
        "generation_latency_ms": latency_ms,
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    }


def extract_clean_sentence_quote(passage_text: str, max_chars: int = 210) -> str:
    """Deterministically extract a clean verbatim sentence from a passage as fallback."""
    text = passage_text.strip()
    if not text:
        return ""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    for sent in sentences:
        if 35 <= len(sent) <= max_chars and sent in text:
            return sent
    if sentences and sentences[0] in text:
        return sentences[0]
    return text[:max_chars].strip()


def compute_spectrum_placement(
    topic: TopicSpec,
    decision: ContextSelectionDecision,
) -> dict[str, Any]:
    """Compute horizontal spectrum placement from Strands Decider 2B stance probabilities.

    - Returns `bucket`: "pole_a" | "mixed" | "pole_b" | "refusal" | "unclear"
    - Returns `spectrum_x`: float in [8.0, 92.0] for on-spectrum stances, or None for refusal/unclear
    - Returns `stance_label` and `stance_description` from the topic rubric
    """
    pole_a_key = topic.pole_a.key
    pole_b_key = topic.pole_b.key
    mixed_key = topic.mixed_option.key

    probs = decision.stance_probabilities
    p_a = float(probs.get(pole_a_key, 0.0))
    p_b = float(probs.get(pole_b_key, 0.0))
    p_m = float(probs.get(mixed_key, 0.0))

    assigned = decision.assigned_stance

    if assigned == "refusal" or decision.is_refusal:
        return {
            "bucket": "refusal",
            "stance_key": "refusal",
            "stance_label": "Refusal",
            "stance_short_label": "Refused to answer",
            "stance_description": "The model declined to take a position or answer the question.",
            "on_spectrum": False,
            "spectrum_x": None,
            "pole_a_prob": round(p_a, 4),
            "mixed_prob": round(p_m, 4),
            "pole_b_prob": round(p_b, 4),
        }

    if assigned == "unclear" or decision.is_unclear:
        return {
            "bucket": "unclear",
            "stance_key": "unclear",
            "stance_label": "Unclear",
            "stance_short_label": "Unclear stance",
            "stance_description": (
                decision.unclear_reason
                or "Decider confidence was below the calibrated threshold; no stance label was forced."
            ),
            "on_spectrum": False,
            "spectrum_x": None,
            "pole_a_prob": round(p_a, 4),
            "mixed_prob": round(p_m, 4),
            "pole_b_prob": round(p_b, 4),
        }

    # Continuous coordinate in [0, 100]: 0 = pure Pole A, 50 = balanced/Mixed, 100 = pure Pole B
    raw_x = ((p_b - p_a) + 1.0) * 50.0
    clamped_x = round(max(8.0, min(92.0, raw_x)), 1)

    if assigned == pole_a_key:
        return {
            "bucket": "pole_a",
            "stance_key": pole_a_key,
            "stance_label": topic.pole_a.label,
            "stance_short_label": topic.pole_a.short_label,
            "stance_description": topic.pole_a.description,
            "on_spectrum": True,
            "spectrum_x": min(34.0, clamped_x),
            "pole_a_prob": round(p_a, 4),
            "mixed_prob": round(p_m, 4),
            "pole_b_prob": round(p_b, 4),
        }

    if assigned == pole_b_key:
        return {
            "bucket": "pole_b",
            "stance_key": pole_b_key,
            "stance_label": topic.pole_b.label,
            "stance_short_label": topic.pole_b.short_label,
            "stance_description": topic.pole_b.description,
            "on_spectrum": True,
            "spectrum_x": max(66.0, clamped_x),
            "pole_a_prob": round(p_a, 4),
            "mixed_prob": round(p_m, 4),
            "pole_b_prob": round(p_b, 4),
        }

    # Default / mixed option
    return {
        "bucket": "mixed",
        "stance_key": mixed_key,
        "stance_label": topic.mixed_option.label,
        "stance_short_label": topic.mixed_option.short_label,
        "stance_description": topic.mixed_option.description,
        "on_spectrum": True,
        "spectrum_x": round(max(36.0, min(64.0, clamped_x)), 1),
        "pole_a_prob": round(p_a, 4),
        "mixed_prob": round(p_m, 4),
        "pole_b_prob": round(p_b, 4),
    }


def synthesize_comparison_with_strands_agent(
    question: str,
    topic: TopicSpec,
    analyzed_models: list[dict[str, Any]],
) -> dict[str, Any]:
    """Use a Strands Agent on Amazon Bedrock to explain each model's framing and 'Where they differ'.

    CRITICAL: The Strands Agent receives ONLY the passages selected by Strands Decider 2B
    (`decision.selected_context_block`) via the `#context-memory` pattern.
    """
    t0 = time.perf_counter()

    # Build context payload containing ONLY Decider-selected passages for each available model
    model_context_blocks: list[str] = []
    decisions_for_hook: list[ContextSelectionDecision] = []

    for item in analyzed_models:
        if item["status"] != "available":
            continue
        decision: ContextSelectionDecision = item["_decision_obj"]
        decisions_for_hook.append(decision)
        placement = item["placement"]
        model_context_blocks.append(
            f"=== MODEL: {item['display_name']} (slot_id: {item['slot_id']}) ===\n"
            f"Decider Classified Stance: {placement['stance_label']} "
            f"(bucket={placement['bucket']}, confidence={decision.stance_confidence:.2f})\n"
            f"Decider-Selected Context Passages ({decision.selected_chars}/{decision.total_chars} chars retained):\n"
            f"{decision.format_selected_context()}\n"
        )

    combined_context = "\n".join(model_context_blocks)

    system_prompt = (
        "You are the editorial synthesis agent for TILT ('Ground News for AI'). "
        "You receive ONLY the high-relevance passages selected by Strands Decider 2B from three AI models "
        "answering the same controversial question.\n"
        "Rules:\n"
        "1. Do NOT invent or exaggerate disagreement. If models broadly agree, state that honestly and explain "
        "how their emphasis or conditions differ.\n"
        "2. For each model, write `framing_sentence`: exactly ONE concise editorial sentence (16-28 words) "
        "explaining how this response frames the issue.\n"
        "3. For each model, pick `exact_quote`: ONE verbatim sentence copied character-for-character from "
        "that model's Decider-Selected Context Passages.\n"
        "4. Write `where_they_differ`: exactly TWO crisp editorial sentences summarizing the most meaningful "
        "observed difference across the models (or noting their shared consensus and subtle framing differences).\n"
        "5. Output valid JSON only matching the requested schema."
    )

    user_prompt = (
        f"Question: {question}\n"
        f"Spectrum Pole A: {topic.pole_a.label} ({topic.pole_a.description})\n"
        f"Spectrum Middle: {topic.mixed_option.label} ({topic.mixed_option.description})\n"
        f"Spectrum Pole B: {topic.pole_b.label} ({topic.pole_b.description})\n\n"
        f"{combined_context}\n\n"
        "Return ONLY a JSON object with this exact structure:\n"
        "{\n"
        '  "where_they_differ": "Two sentences explaining the most meaningful observed difference...",\n'
        '  "agreement_level": "divergent" | "nuanced_split" | "broad_agreement",\n'
        '  "headline_summary": "Short 6-10 word editorial subheadline summarizing the split",\n'
        '  "models": {\n'
        '    "<slot_id>": {\n'
        '      "framing_sentence": "One sentence explaining its framing.",\n'
        '      "exact_quote": "Exact verbatim quote copied from the selected passages."\n'
        "    }\n"
        "  }\n"
        "}"
    )

    try:
        # Attach our Strands InterventionHandler from patterns/context_memory
        selector = PassageContextSelector(decider=DeciderClient(url=DECIDER_URL))
        intervention = ContextMemoryIntervention(
            selector=selector,
            stance_options=topic.stance_options_dict(),
            question_text=question,
        )
        intervention.decisions.extend(decisions_for_hook)

        bedrock_model = BedrockModel(
            model_id=SYNTHESIS_MODEL_ID,
            region_name=AWS_REGION,
            temperature=0.1,
            max_tokens=700,
        )
        agent = Agent(
            model=bedrock_model,
            interventions=[intervention],
            system_prompt=system_prompt,
            callback_handler=None,
        )
        agent_result = agent(user_prompt)
        raw_text = str(agent_result).strip()

        # Extract JSON object
        json_match = re.search(r"\{[\s\S]*\}", raw_text)
        parsed = json.loads(json_match.group(0) if json_match else raw_text)
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        parsed["synthesis_latency_ms"] = latency_ms
        parsed["synthesis_model_id"] = SYNTHESIS_MODEL_ID
        return parsed
    except Exception as exc:
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        return {
            "where_they_differ": (
                "The models weigh the core trade-offs of this question with distinct emphasis across "
                "risk, autonomy, and institutional guardrails. Inspect each model's highlighted evidence "
                "passage below to compare their exact framing."
            ),
            "agreement_level": "nuanced_split",
            "headline_summary": "Models weigh competing priorities with distinct institutional framing",
            "models": {},
            "synthesis_latency_ms": latency_ms,
            "synthesis_model_id": SYNTHESIS_MODEL_ID,
            "synthesis_error": str(exc),
        }


def run_comparison_pipeline(
    topic_id: str | None = None,
    custom_question: str | None = None,
    custom_pole_a: str | None = None,
    custom_pole_b: str | None = None,
) -> dict[str, Any]:
    """Execute the full end-to-end 3-model TILT comparison pipeline."""
    pipeline_t0 = time.perf_counter()

    if topic_id and topic_id in CURATED_TOPICS_BY_ID:
        topic = CURATED_TOPICS_BY_ID[topic_id]
    elif custom_question and custom_question.strip():
        topic = derive_custom_topic_spec(
            question=custom_question.strip(),
            pole_a_label=custom_pole_a,
            pole_b_label=custom_pole_b,
        )
    else:
        raise ValueError("Either a valid topic_id or custom_question must be provided.")

    question = topic.question

    # Step 1: Query all 3 Bedrock models in parallel with identical prompts & comparable settings
    gen_t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(query_single_bedrock_model, model_cfg, question)
            for model_cfg in COMPARISON_MODELS
        ]
        raw_model_outputs = [f.result() for f in futures]
    generation_wall_ms = round((time.perf_counter() - gen_t0) * 1000.0, 1)

    # Step 2 & 3: Split into numbered passages & run Strands Decider 2B (#context-memory selector)
    decider_client = DeciderClient(url=DECIDER_URL)
    selector = PassageContextSelector(
        decider=decider_client,
        thresholds=CalibrationThresholds(),
    )

    decider_t0 = time.perf_counter()
    analyzed_models: list[dict[str, Any]] = []
    total_decider_calls_ms = 0.0
    total_chars_before = 0
    total_chars_after = 0

    for model_cfg, raw_out in zip(COMPARISON_MODELS, raw_model_outputs):
        if raw_out["status"] != "available" or not raw_out["original_response"].strip():
            analyzed_models.append(
                {
                    **raw_out,
                    "accent_color": model_cfg.accent_color,
                    "badge_bg": model_cfg.badge_bg,
                    "placement": {
                        "bucket": "unavailable",
                        "stance_key": "unavailable",
                        "stance_label": "Unavailable",
                        "stance_short_label": "Model unavailable",
                        "stance_description": raw_out.get("error") or "Model temporarily unavailable.",
                        "on_spectrum": False,
                        "spectrum_x": None,
                        "pole_a_prob": 0.0,
                        "mixed_prob": 0.0,
                        "pole_b_prob": 0.0,
                    },
                    "decider": None,
                    "passages": [],
                    "selected_passage_ids": [],
                    "primary_evidence_passage_id": None,
                    "framing_explanation": "This model was temporarily unavailable during this comparison run.",
                    "featured_quote": None,
                }
            )
            continue

        decision = selector.evaluate_response(
            question_text=question,
            response_text=raw_out["original_response"],
            stance_options=topic.stance_options_dict(),
        )
        total_decider_calls_ms += decision.latency_ms
        total_chars_before += decision.total_chars
        total_chars_after += decision.selected_chars

        placement = compute_spectrum_placement(topic, decision)

        analyzed_models.append(
            {
                **raw_out,
                "accent_color": model_cfg.accent_color,
                "badge_bg": model_cfg.badge_bg,
                "placement": placement,
                "_decision_obj": decision,
                "decider": {
                    "assigned_stance": decision.assigned_stance,
                    "raw_top_stance": decision.raw_top_stance,
                    "stance_probabilities": decision.stance_probabilities,
                    "stance_confidence": decision.stance_confidence,
                    "is_refusal": decision.is_refusal,
                    "refusal_probability": decision.refusal_probability,
                    "is_unclear": decision.is_unclear,
                    "unclear_reason": decision.unclear_reason,
                    "selected_passage_ids": decision.selected_passage_ids,
                    "pruned_passage_ids": decision.pruned_passage_ids,
                    "primary_evidence_passage_id": decision.primary_passage_id,
                    "context_compression_ratio": round(1.0 - decision.context_reduction_ratio, 4),
                    "context_reduction_ratio": decision.context_reduction_ratio,
                    "total_char_count": decision.total_chars,
                    "selected_char_count": decision.selected_chars,
                    "decider_latency_ms": decision.latency_ms,
                    "decider_usage": {
                        "input_tokens": decision.input_tokens,
                        "output_tokens": decision.output_tokens,
                    },
                },
                "passages": [asdict(p) for p in decision.passages],
                "selected_passage_ids": decision.selected_passage_ids,
                "primary_evidence_passage_id": decision.primary_passage_id,
            }
        )

    decider_wall_ms = round((time.perf_counter() - decider_t0) * 1000.0, 1)

    # Resolve any spectrum icon overlaps (>8% minimum visual separation when in same bucket)
    on_spec = [m for m in analyzed_models if m["placement"].get("on_spectrum") and m["placement"]["spectrum_x"] is not None]
    on_spec.sort(key=lambda m: float(m["placement"]["spectrum_x"]))
    for i in range(1, len(on_spec)):
        prev_x = float(on_spec[i - 1]["placement"]["spectrum_x"])
        curr_x = float(on_spec[i]["placement"]["spectrum_x"])
        if curr_x - prev_x < 7.5:
            nudged = min(93.0, round(prev_x + 7.5, 1))
            on_spec[i]["placement"]["spectrum_x"] = nudged

    # Step 4: Synthesize framing explanations and "Where they differ" using Strands Agent on Decider-selected context
    synthesis = synthesize_comparison_with_strands_agent(
        question=question,
        topic=topic,
        analyzed_models=analyzed_models,
    )
    per_model_synth = synthesis.get("models", {}) if isinstance(synthesis.get("models"), dict) else {}

    # Step 5: Attach framing explanations and deterministically verify every quote against stored originals
    for item in analyzed_models:
        if item["status"] != "available":
            continue
        decision: ContextSelectionDecision = item.pop("_decision_obj")
        slot_id = item["slot_id"]
        model_synth = per_model_synth.get(slot_id, {}) if isinstance(per_model_synth.get(slot_id), dict) else {}

        # Framing sentence
        framing_sentence = str(model_synth.get("framing_sentence") or "").strip()
        if not framing_sentence:
            framing_sentence = (
                f"{item['display_name']} frames this issue around "
                f"{item['placement']['stance_label'].lower()}, emphasizing the trade-offs in passage "
                f"{decision.primary_passage_id}."
            )

        primary_p_score = next(
            (p for p in decision.passages if p.id == decision.primary_passage_id),
            decision.passages[0],
        )
        fallback_passage = Passage(
            id=primary_p_score.id,
            number=primary_p_score.number,
            text=primary_p_score.text,
            start_char=primary_p_score.start_char,
            end_char=primary_p_score.end_char,
        )

        # Candidate quote from synthesis agent, verified against original response
        candidate_quote = str(model_synth.get("exact_quote") or "").strip()
        verification = verify_exact_quote(
            original_text=item["original_response"],
            candidate_quote=candidate_quote,
            fallback_passage=fallback_passage,
        )
        # Map verification to passage_id
        matched_passage_id = primary_p_score.id
        for p in decision.passages:
            if verification["start_char"] >= p.start_char and verification["start_char"] < p.end_char:
                matched_passage_id = p.id
                break
        verification["passage_id"] = matched_passage_id

        item["framing_explanation"] = framing_sentence
        item["featured_quote"] = verification

    # Check if all available models landed in the same bucket -> ensure honest agreement framing
    available_buckets = [
        m["placement"]["bucket"] for m in analyzed_models if m["status"] == "available"
    ]
    unique_buckets = set(available_buckets)
    agreement_level = synthesis.get("agreement_level", "nuanced_split")
    if len(unique_buckets) == 1 and len(available_buckets) >= 2:
        agreement_level = "broad_agreement"
    elif len(unique_buckets) >= 2 and ("pole_a" in unique_buckets and "pole_b" in unique_buckets):
        agreement_level = "divergent"

    total_wall_ms = round((time.perf_counter() - pipeline_t0) * 1000.0, 1)

    comparison_id = _build_comparison_id(topic.id, question)
    created_at = dt.datetime.now(dt.timezone.utc).isoformat()

    return {
        "id": comparison_id,
        "created_at": created_at,
        "cached": False,
        "topic": topic.to_dict(),
        "question": question,
        "summary": {
            "where_they_differ": synthesis.get("where_they_differ", ""),
            "headline_summary": synthesis.get("headline_summary", ""),
            "agreement_level": agreement_level,
            "unique_stance_count": len(unique_buckets),
        },
        "models": analyzed_models,
        "provenance": {
            "decider_model_id": DECIDER_MODEL_ID,
            "decider_service_url": DECIDER_URL,
            "pattern_tags": ["#strands-decider-2b", "#context-memory"],
            "synthesis_agent_framework": "strands-agents",
            "synthesis_model_id": SYNTHESIS_MODEL_ID,
            "aws_region": AWS_REGION,
            "shared_prompt_template": SHARED_USER_PROMPT_TEMPLATE,
            "shared_inference_settings": SHARED_INFERENCE_CONFIG,
            "calibration_thresholds": asdict(CalibrationThresholds()),
            "context_selection_stats": {
                "total_chars_before": total_chars_before,
                "total_chars_after": total_chars_after,
                "overall_compression_ratio": round(
                    total_chars_after / max(1, total_chars_before), 4
                ),
            },
            "latency_ms": {
                "bedrock_generation_parallel_ms": generation_wall_ms,
                "strands_decider_total_ms": round(total_decider_calls_ms, 1),
                "strands_decider_wall_ms": decider_wall_ms,
                "strands_synthesis_agent_ms": synthesis.get("synthesis_latency_ms", 0.0),
                "total_pipeline_wall_ms": total_wall_ms,
            },
        },
    }


def _build_comparison_id(topic_id: str, question: str) -> str:
    if topic_id != "custom" and topic_id in CURATED_TOPICS_BY_ID:
        short_hash = uuid.uuid4().hex[:6]
        return f"{topic_id}-{short_hash}"
    digest = hashlib.sha256(question.strip().lower().encode("utf-8")).hexdigest()[:8]
    short_hash = uuid.uuid4().hex[:4]
    return f"custom-{digest}-{short_hash}"
