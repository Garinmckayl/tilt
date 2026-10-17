"""Runnable example of the #context-memory Strands Decider 2B pattern inside a Strands Agent.

Tags: #strands-decider-2b #context-memory

Run with:
    # 1. Start the persistent Strands Decider 2B server (if not already running):
    strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8099

    # 2. Run the Strands Agent example:
    python patterns/context_memory/example_strands_agent.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from strands import Agent, tool
from patterns.context_memory import (
    ContextMemoryIntervention,
    DeciderClient,
    PassageContextSelector,
    ServerUnavailable,
)

QUESTION = "Should schools ban smartphones?"
STANCE_OPTIONS = {
    "opposes_ban": "Opposes a ban: argues against banning smartphones in schools, favoring integration, digital literacy, or student autonomy.",
    "mixed": "Mixed / conditional: weighs both sides equally or favors classroom-only teacher rules without a full school-day ban.",
    "supports_ban": "Supports a ban: argues in favor of banning or strictly restricting smartphones during the school day.",
}

SAMPLE_MODEL_RESPONSE = (
    "In an era of ubiquitous connectivity, schools face a difficult question over student devices. "
    "Before looking at policy, it helps to note that smartphones were introduced in the late 2000s and quickly became common among teenagers.\n\n"
    "Schools should implement bell-to-bell smartphone bans because constant notification loops fragment adolescent attention and measurably degrade classroom learning. "
    "Longitudinal studies across school districts in the UK, Spain, and the US demonstrate that removing phones improves test scores by 6% to 14% for lower-achieving students while cutting schoolyard cyberbullying.\n\n"
    "While parents understandably want a way to coordinate after-school pickup, schools can easily accommodate this by keeping phones locked in Yondr pouches until the final bell."
)


@tool
def summarize_selected_evidence(
    response_text: str,
    selected_context: str = "",
    assigned_stance: str = "",
    primary_quote: str = "",
    stance_confidence: float = 0.0,
) -> str:
    """Inspect only the Strands Decider 2B selected passages and return structured evidence.

    Args:
        response_text: The raw model response to analyze.
    """
    return json.dumps(
        {
            "assigned_stance": assigned_stance,
            "stance_confidence": stance_confidence,
            "primary_quote": primary_quote,
            "selected_context_passed_to_agent": selected_context,
        },
        indent=2,
    )


def main() -> int:
    decider = DeciderClient()
    try:
        health = decider.health()
        print(f"[strands-decider] connected to {health['checkpoint']} on {health['device']}")
    except ServerUnavailable as exc:
        print(exc)
        return 1

    selector = PassageContextSelector(decider=decider)
    intervention = ContextMemoryIntervention(
        selector=selector,
        stance_options=STANCE_OPTIONS,
        question_text=QUESTION,
    )

    agent = Agent(
        model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        tools=[summarize_selected_evidence],
        interventions=[intervention],
        system_prompt=(
            "You are an editorial analyst. Call `summarize_selected_evidence` with the provided "
            "response_text, then explain the response's framing in one concise sentence using ONLY "
            "the selected context returned by the tool."
        ),
        callback_handler=None,
    )

    prompt = f"Analyze this response to '{QUESTION}':\n\n{SAMPLE_MODEL_RESPONSE}"
    result = agent(prompt)

    decision = intervention.decisions[0]
    print("\n--- Strands Decider 2B #context-memory Decision ---")
    print(f"Assigned Stance    : {decision.assigned_stance} (confidence={decision.stance_confidence:.3f})")
    print(f"Refusal Prob       : {decision.refusal_probability:.4f} (is_refusal={decision.is_refusal})")
    print(f"Selected Passages  : {decision.selected_passage_ids} (pruned={decision.pruned_passage_ids})")
    print(f"Context Reduction  : {decision.context_reduction_ratio * 100:.1f}% chars removed before synthesis")
    print(f"Primary Quote      : \"{decision.primary_quote}\"")
    print(f"Decider Latency    : {decision.latency_ms:.1f} ms ({decision.input_tokens} input tokens)")
    print(f"\n--- Strands Agent Output (Amazon Bedrock) ---\n{result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
