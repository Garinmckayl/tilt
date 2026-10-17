# TILT: Ground News for AI

**Tags:** `#strands-decider-2b` `#context-memory` `#strands-agents` `#amazon-bedrock`

![TILT Masthead](assets/tilt-masthead.png)

> **Before you let AI shape your opinion, see how other AIs answer.**  
> **Live Deployment (AWS):** [https://tilt.arcumet.com](https://tilt.arcumet.com) · [https://tilt.35-166-228-8.sslip.io](https://tilt.35-166-228-8.sslip.io)  
> **Demo Video (`demo/tilt-demo.mp4`):** [https://tilt.35-166-228-8.sslip.io/demo.mp4](https://tilt.35-166-228-8.sslip.io/demo.mp4)  
> **GitHub Repository:** [https://github.com/Garinmckayl/tilt](https://github.com/Garinmckayl/tilt)

---

## 1. Millions of People Ask AI What to Believe. But Whose Perspective Are They Getting?

When someone asks an AI chatbot about a war, their rights, religion, immigration, nuclear power, or a controversial policy, they usually receive one confident answer without seeing its assumptions.

Even when prompted with the exact same question at the same temperature, different foundation models weigh institutional rules, individual autonomy, economic tradeoffs, and social risks differently. The chatbot you choose can shape the perspective you receive.

**TILT asks leading AIs the same question and exposes their differences side by side, so you can see the framing before it shapes your judgment.**

![TILT Comparison Preview](assets/tilt-comparison-preview.png)

### A Concrete Example: “Should schools ban smartphones?”

When **Anthropic Claude Sonnet 4.5**, **Meta Llama 3.3 70B**, and **DeepSeek V3.2** answer *"Should schools ban smartphones?"* under identical settings (`temperature=0.3`, `maxTokens=260`) on Amazon Bedrock, TILT shows three answers, where their stances differ, and the exact passages supporting each label:

1. **DeepSeek V3.2 (`Supports a ban`, spectrum position `72%`):**
   - **Framing:** Argues for a school-day ban to protect academic focus and student mental health.
   - **Verified Supporting Passage (`[P1]`):** *"Yes, schools should implement bans or strict restrictions on smartphones during the school day. The evidence is clear that constant access to phones is a major source of distraction, negatively impacting academic performance and classroom focus."*
2. **Claude Sonnet 4.5 (`Classroom restrictions only`, spectrum position `46%`):**
   - **Framing:** Balances classroom distraction concerns against educational tools and emergency communication.
   - **Verified Supporting Passage (`[P2]`):** *"A more nuanced approach might work better: restricting phone use during instructional time and allowing it during breaks, or implementing \"phone-free zones\" in classrooms while permitting controlled use elsewhere."*
3. **Llama 3.3 70B (`Classroom restrictions only`, spectrum position `54%`):**
   - **Framing:** Endorses class-hour limits while emphasizing digital literacy and self-regulation.
   - **Verified Supporting Passage (`[P3]`):** *"A middle ground, such as restricting phone use during class hours, may be the most effective approach, balancing academic focus with practical considerations."*

### More Observed Comparisons Across Policy, Rights, and Energy

- **Creators' & Workers' Rights (*“Should training AI models on copyrighted works require explicit creator opt-in?”*):** Llama 3.3 70B lands on **Require creator opt-in** (`92%` confidence), prioritizing creator consent over intellectual property. Claude Sonnet 4.5 and DeepSeek V3.2 land on **Opt-out & licensing pools**, arguing that universal opt-in is impractical at web scale and proposing collective licensing instead.
- **Nuclear Energy (*“Should governments aggressively expand nuclear power to meet climate goals?”*):** DeepSeek V3.2 emphasizes nuclear as essential for zero-carbon baseload power, while Claude Sonnet 4.5 and Llama 3.3 70B stress that nuclear should complement, not crowd out, faster-deploying renewables and storage. When models broadly agree, TILT shows that agreement honestly while highlighting differences in emphasis.
- **Universal Basic Income (*“Should governments introduce a Universal Basic Income to offset AI job displacement?”*):** Llama 3.3 70B and DeepSeek V3.2 support proactive UBI (`Supports UBI`), whereas Claude Sonnet 4.5 favors targeted transition support and pilot programs first (`Targeted transition support`).

Clicking any stance label or spectrum pin expands the full model response and highlights the exact supporting passage. These labels describe these particular responses; they do not claim to reveal permanent model beliefs.

---

## 2. How Strands Decider 2B Powers Stance Placement & `#context-memory` Selection

![TILT Architecture](assets/tilt-architecture.png)

A naive multi-model comparison pipeline uses a generative LLM both to classify stances and to summarize full, unfiltered model responses. That approach has three practical problems:
- **Forced labels on ambiguous responses:** Generative judges routinely guess a stance even when a response is evasive, off-topic, or genuinely split, without calibrated probabilities.
- **Context bloat & quote drift:** Passing three full verbose responses into a downstream synthesis agent wastes tokens and risks pulling quotes from introductory filler rather than the core argument.
- **High latency & token cost:** Calling a frontier LLM for every classification, refusal check, and passage-scoring step multiplies latency and API spend.

TILT solves this with a reusable **`#context-memory` passage-selection decision pattern** (`patterns/context_memory/`) powered by **Strands Decider 2B** (`StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`).

### Shared-Prefix System One Formulation

For each model response, TILT splits the text into numbered passages (`[P1]`, `[P2]`, ..., `[PN]`) with exact character offsets (`start_char`, `end_char`) and sends **one shared-prefix request** to `POST /v1/systemone`:

```python
state = f"Question: {question_text}\n\nResponse Passages:\n{numbered_block}"

questions = {
    # 1. Refusal separation (Noul -> P(true) in [0, 1])
    "is_refusal": DeciderClient.noul(
        "Does the response refuse or decline to answer the question?",
        criteria={
            "true": "Refuses or declines to answer the question or states it cannot take a stance.",
            "false": "Addresses the question with arguments, analysis, or a position.",
        },
    ),
    # 2. Topic-specific stance classification (Choice -> probabilities + calibrated confidence)
    "stance": DeciderClient.choice(
        f"Classify the overall stance of this response on '{question_text}'.",
        criteria=stance_options,  # Pole A, Mixed/Conditional, Pole B
    ),
    # 3. Per-passage relevance scoring (Score -> expected value on 0..3 rubric)
    "rel_P1": DeciderClient.score(
        f"Rate how directly passage P1 supports the stance on '{question_text}'.",
        criteria=PASSAGE_RELEVANCE_RUBRIC,
    ),
    # ... rel_P2 .. rel_PN ...
    # 4. Primary evidence passage pointer (Choice over P1..PN)
    "best_passage": DeciderClient.choice(
        f"Select the single passage that best states the core thesis on '{question_text}'.",
        criteria={pid: f"Passage {pid} states the core stance." for pid, _ in passages},
    ),
}
```

Because `StrandsDeciderModel` encodes the `state` prefix **once** into its KV cache (across its 18 Gated DeltaNet linear-attention layers and 6 full-attention layers) and evaluates all question suffixes in one batched forward pass, TILT obtains refusal probability, stance distribution, per-passage relevance scores, and the primary evidence pointer in a single round-trip.

### Material Control Over Stance Placement & Context Pruning

Strands Decider 2B directly controls two behaviors in the pipeline:
1. **Stance Placement, Refusal Separation & "Unclear" Gating:**
   - If `P(is_refusal) >= 0.75`, the response is routed to a separate **Refusal** tray off the stance spectrum.
   - If `max(rel_P1..PN) < 1.45` (on the `0..3` rubric) or `stance_confidence < 0.25` without a consensus middle ground, the response is labeled **Unclear** rather than forced onto the spectrum.
   - Otherwise, the continuous spectrum coordinate `x` is computed directly from Decider's probability distribution `(P(Pole B) - P(Pole A) + 1) * 50`.
2. **Context Pruning (`#context-memory`) for the Strands Synthesis Agent:**
   - Passages scoring below the calibrated relevance threshold (`1.50 / 3.00`) are pruned, reducing input context characters by **34% to 39%** before the downstream `strands.Agent` on Amazon Bedrock synthesizes each model's 1-sentence framing and the 2-sentence **"Where they differ"** summary.
   - Finally, `verify_exact_quote()` deterministically checks that every displayed quotation is an exact substring of the stored original response (`original_response[start_char:end_char]`).

---

## 3. What We Learned Optimizing Strands Decider 2B on AWS CPU

Our deployment runs on an AWS `m7i.xlarge` instance (`Intel Xeon Platinum 8488C` Sapphire Rapids with hardware **AMX-BF16** matrix extensions). While profiling `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`, we identified and resolved two performance bottlenecks:

1. **LoRA Adapter Merge + AMX-BF16 + Block-Inversion Gated DeltaNet Kernel (`2.3x` speedup, `53%` RAM reduction):**
   - By default, loading `Qwen3.5-2B` on CPU casts weights to `float32` (`~7.5 GB` RSS) and runs unmerged LoRA adapters across all 7 linear projections per layer.
   - In `backend/decider_service.py`, we merge the rank-16 LoRA adapter into the base weights at startup (`merge_and_unload()`), convert the torso to `bfloat16` to use Intel Sapphire Rapids hardware **AMX-BF16** instructions (`~3.5 GB` RSS), and keep the vectorized Neumann block-inversion chunk kernel active.
2. **Uniform Question Suffix Lengths in Shared-Prefix Batches (`2.7x` batch speedup):**
   - When multiple questions share a state in `/v1/systemone`, `StrandsDeciderModel._pad(q)` right-pads all question token sequences to the length of the longest question. Previously, embedding full passage text inside `best_passage` criteria inflated `best_passage` to 430 tokens while `rel_P1..PN` were 95 tokens, causing 75% of the batch compute to process `<pad>` tokens.
   - By referencing passage IDs (`P1..PN`) already present in the shared `state` prefix, all question suffixes stay tightly bounded (`53 to 96` tokens), dropping a 7-question shared-prefix batch from `10.69s` down to **`3.85s` mean** (`1.04s` p50 for a single question).

---

## 4. Evaluation & Measured Latency Results

We evaluated the pipeline on an initial human-labeled test set of 13 examples (`evaluation/human_labeled_dataset.json` and `evaluation/run_evaluation.py`) spanning clear Pole A/B stances, conditional/mixed stances, explicit refusals, and "unclear" examples (off-topic answers and high-lexical-overlap non-answers).

| Metric | Result | Details |
| :--- | :--- | :--- |
| **Stance Classification** | **13/13 correct on our initial labeled test set** | Joint confidence (`>= 0.25`) + evidence relevance (`>= 1.45`) gating |
| **Refusal Separation** | **13/13 correct on our initial labeled test set** | Noul threshold `P(true) >= 0.75` |
| **Passage Selection Precision** | **100.0%** | Zero filler or introductory passages leaked into agent context |
| **Passage Selection Recall** | **94.4%** | Retained 17/18 labeled core argument passages |
| **Passage Selection F1** | **97.1%** | Mean context reduction of **34.0%** across test set responses |
| **Primary Evidence Match** | **13/13** | Top-ranked Decider passage matched human-labeled primary evidence |
| **Single-Question Latency (AWS)** | **1,037 ms p50** | Persistent `tilt-decider.service` on `m7i.xlarge` |
| **7-Question Shared-Prefix Batch** | **3,847 ms mean** | Evaluates refusal + stance + 4 passage scores + pointer in 1 call (`~550 ms`/question) |

### Measured Comparison: Strands Decider 2B Shared-Prefix vs. Generative LLM Judge

Evaluating 7 structured decisions per model response across 3 models (21 decisions per comparison) with Strands Decider 2B's shared-prefix KV cache compared to sequential frontier LLM judge calls on AWS `us-east-1`:

| Dimension | Generative LLM Judge (Claude Sonnet 4.5) | Strands Decider 2B Shared-Prefix (`/v1/systemone`) | Measured Difference |
| :--- | :--- | :--- | :--- |
| **Per-Decision Latency** | `~3,520 ms` per structured rubric call | **`1,037 ms` p50** single · **`550 ms` / question** in 7-question batch | **6.4x faster per decision** |
| **Downstream Agent Input Context (`#context-memory`)** | `100%` (all raw paragraphs sent to synthesis agent) | **`61% to 66%` retained** (passages scored `< 1.50/3.0` pruned) | **34% to 39% context reduction** |
| **Total Bedrock Token Spend per 3-Model Comparison** | `~6,900` tokens (21 judge calls + unpruned synthesis) | **`~1,480` tokens** (`0` Bedrock tokens for 21 local Decider decisions + pruned synthesis) | **78% fewer Bedrock tokens** |

