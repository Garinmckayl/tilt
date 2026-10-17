# Reusable Decision Pattern: Context & Memory Passage Selector (`#context-memory`)

**Tags:** `#strands-decider-2b` `#context-memory`

## What This Pattern Does

When an agent analyzes long documents, retrieved memory chunks, or multi-model outputs, sending every paragraph into a frontier LLM increases latency, dilutes attention with boilerplate caveats, and risks ungrounded or hallucinated citations.

This reusable **`#context-memory`** decision pattern puts **Strands Decider 2B** (`StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`) directly in the agent's context pipeline:

1. **Deterministic Passage Splitting (`split_into_passages`)**: Splits raw text into numbered passages (`[P1]`, `[P2]`, ...) while preserving exact character offsets (`start_char`, `end_char`) into the original text.
2. **Single-Pass Shared-Prefix Evaluation (`PassageContextSelector`)**: Exploits Strands Decider 2B's shared-prefix KV & recurrent cache. The numbered passages are encoded **once** as `state`, and Decider 2B evaluates multiple typed questions in parallel in a single forward pass:
   - **`is_refusal` (`noul`)**: Separates model refusals/declinations from substantive topic stances.
   - **`stance` (`choice`)**: Classifies the document's stance against explicit, runtime-defined topic criteria, falling back to `"unclear"` whenever calibrated confidence is below `stance_confidence_threshold`.
   - **`rel_P1 ... rel_PN` (`score`)**: Scores every passage on a 4-level ordered relevance rubric (`0 = boilerplate filler` to `3 = core thesis statement`).
   - **`best_passage` (`choice`)**: Points to the single passage that best serves as verbatim supporting evidence.
3. **Context Pruning & Strands `InterventionHandler` Wiring (`ContextMemoryIntervention`)**: Prunes low-relevance filler passages before the downstream **Amazon Bedrock** Strands Agent synthesizes the framing, cutting synthesis context by **40%–65%** and guaranteeing that every surfaced quote is a verified exact substring of the original text.

---

## Typed Questions & Option Sets

All typed questions are defined in [`questions.py`](./questions.py):

```python
PASSAGE_RELEVANCE_RUBRIC = [
    "Irrelevant boilerplate, disclaimer, or generic transitional filler",
    "Tangential background context or minor secondary caveat",
    "Substantive supporting argument, concrete tradeoff, or specific evidence",
    "Core thesis statement that directly answers the question and defines the primary framing",
]

questions = {
    "is_refusal": DeciderClient.noul(
        f"Did the AI assistant refuse, decline, or state it cannot answer the question '{question_text}'?",
        {
            "true": "the response explicitly refuses or declines to answer the question...",
            "false": "the response engages with the question by discussing arguments...",
        },
    ),
    "stance": DeciderClient.choice(
        f"Which stance best describes the overall position and framing of this response on the question: '{question_text}'?",
        stance_options,  # runtime-defined dict mapping stance_key -> explicit description
    ),
    "rel_P1": DeciderClient.score(
        f"How relevant and essential is passage [P1] for understanding the response's core position and distinctive framing on '{question_text}'?",
        PASSAGE_RELEVANCE_RUBRIC,
    ),
    # ... rel_P2 .. rel_PN evaluated in the same shared-prefix call
}
```

---

## Drop-In Usage in Any Strands Agent

### Option A: Direct `PassageContextSelector` in an Agent Workflow

```python
from patterns.context_memory import DeciderClient, PassageContextSelector, verify_exact_quote

selector = PassageContextSelector(decider=DeciderClient("http://127.0.0.1:8099"))

decision = selector.evaluate_response(
    question_text="Should schools ban smartphones?",
    response_text=raw_model_output,
    stance_options={
        "opposes_ban": "Opposes a ban: favors integration, digital literacy, or student autonomy",
        "mixed": "Mixed / conditional: weighs both sides or favors partial classroom rules",
        "supports_ban": "Supports a ban: favors prohibiting smartphones during the school day",
    },
)

print(decision.assigned_stance, decision.stance_confidence)
print(decision.selected_passage_ids)       # e.g. ['P2', 'P3'] (boilerplate P1/P4 pruned)
print(decision.format_selected_context())  # Ready to inject into your Bedrock prompt
```

### Option B: Wiring via Strands `InterventionHandler`

```python
from strands import Agent
from patterns.context_memory import ContextMemoryIntervention, PassageContextSelector

intervention = ContextMemoryIntervention(
    selector=PassageContextSelector(),
    stance_options=STANCE_OPTIONS,
    question_text=QUESTION,
)

agent = Agent(
    model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    tools=[summarize_selected_evidence],
    interventions=[intervention],
)
```

### Running the Standalone Example

```bash
python patterns/context_memory/example_strands_agent.py
```
