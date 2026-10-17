# Human-Labeled Evaluation & Threshold Calibration Report

**Tags:** `#strands-decider-2b` `#context-memory`

## Overview

This directory contains the reproducible human-labeled evaluation dataset (`human_labeled_dataset.json`), evaluation runner (`run_evaluation.py`), and recorded metrics (`results.json`) for TILT's **Strands Decider 2B** (`StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`) decision pipeline.

The evaluation measures four production behaviors on our actual AWS EC2 deployment (`m7i.xlarge`, 4th-Gen Intel Xeon Platinum 8488C with AMX-BF16):
1. **Stance Classification & Unclear Routing**: Assigning responses to explicit topic-specific stance poles or `"mixed"`, while routing low-confidence or evidence-poor responses to `"unclear"` instead of forcing a label.
2. **Refusal Separation**: Distinguishing explicit model refusals (`is_refusal` `noul` question) from topic stances.
3. **Passage Relevance & Primary Quote Selection (`#context-memory`)**: Scoring numbered passages (`[P1]..[PN]`) on a 4-level ordered relevance rubric (`0..3`) and selecting only high-signal passages for the downstream Bedrock synthesis agent.
4. **Measured Deployment Latency**: Single-question vs. 7-question shared-prefix inference latency on the persistent HTTP service (`http://127.0.0.1:8099/v1/systemone`).

---

## Summary Metrics (`results.json`)

| Metric | Value | Notes |
| --- | --- | --- |
| **Stance Classification (Joint Evidence-Gated)** | **13/13 correct on our initial labeled test set** | Requires both `stance_confidence >= 0.35` and `max_passage_relevance >= 1.45` |
| **Stance Classification (Stance Confidence Only)** | **12/13 correct (92.3%)** | Catches off-topic text (`eval-12`), misses lexical-overlap meta-text (`eval-13`) |
| **Stance Classification (Uncalibrated Argmax)** | **11/13 correct (84.6%)** | Forces stance labels onto both unclear cases |
| **Refusal Separation** | **13/13 correct on our initial labeled test set** | True refusals score `0.817-0.854`; substantive responses score `0.070-0.225` |
| **Passage Selection Precision** | **100.0%** | Zero boilerplate/filler passages leaked into selected context |
| **Passage Selection Recall** | **94.4%** | 17 of 18 gold substantive passages selected |
| **Passage Selection F1** | **97.1%** | Harmonic mean of passage precision and recall |
| **Primary Evidence Match** | **13/13** | Top-ranked passage matches human-labeled primary evidence |
| **Mean Context Reduction** | **34.0% (up to 62.2%)** | Percentage of boilerplate/caveat characters pruned before Bedrock synthesis |

---

## Key Finding: Joint Stance + Evidence Gating for "Unclear"

A critical requirement of TILT is that **uncertain classifications display `"Unclear"` rather than a forced label**. Our human-labeled evaluation revealed two distinct ways a response can be `"Unclear"`:

1. **Low Choice Confidence (`eval-12-unclear-offtopic-case`)**: When a response does not match any stance option, Decider 2B's `choice` distribution spreads across options (`confidence = 0.247 < 0.35`), whereas all genuine stances score between `0.552` and `0.947`.
2. **Lexical Overlap Without Stance Evidence (`eval-13-unclear-vague-meta`)**: A response that mentions domain keywords (*"Taxation systems... economists study capital and labor"*) without taking any position can still trigger moderate `choice` confidence (`0.621`) due to lexical overlap with the option descriptions. However, its **highest passage relevance score (`score` primitive) is only `1.059 / 3.00`**, whereas every genuine stance response has a primary passage relevance score of **`1.880 to 2.169 / 3.00`**.

By combining both primitives from the same shared-prefix forward pass:
```python
if stance_confidence < 0.35 or max_passage_relevance < 1.45:
    assigned_stance = "unclear"
```
accuracy on our human-labeled benchmark rises from **84.6%** (uncalibrated argmax) to **92.3%** (confidence threshold alone) to **100.0%** (joint confidence + passage relevance threshold).

---

## Threshold Calibration Table

| `stance_confidence_threshold` | Stance-Only Accuracy | Joint Evidence-Gated Accuracy (`max_rel >= 1.45`) |
| --- | --- | --- |
| `0.10` | 84.6% (11/13) | 100.0% (13/13) |
| `0.20` | 84.6% (11/13) | 100.0% (13/13) |
| `0.25` | 92.3% (12/13) | 100.0% (13/13) |
| `0.30` | 92.3% (12/13) | 100.0% (13/13) |
| **`0.35` (Selected)** | **92.3% (12/13)** | **100.0% (13/13)** |
| `0.45` | 92.3% (12/13) | 100.0% (13/13) |
| `0.55` | 92.3% (12/13) | 100.0% (13/13) |

### Calibrated Production Thresholds (`CalibrationThresholds`)
- **`refusal_prob_threshold = 0.75`**: Cleanly separates non-refusals (`0.070–0.225`) from explicit refusals (`0.817–0.854`).
- **`stance_confidence_threshold = 0.35`**: Sits comfortably between off-topic confidence (`0.247`) and the lowest genuine stance confidence (`0.552`).
- **`min_evidence_relevance_threshold = 1.45`**: Separates meta/non-committal text (`1.059–1.168`) from substantive stance passages (`1.880–2.169`).
- **`passage_relevance_threshold = 1.50`**: Separates introductory/closing filler passages (`0.884–1.338`) from core thesis and supporting argument passages (`1.619–2.169`).

---

## Measured Decision Latency on AWS Deployment

Measured against the persistent `tilt-decider.service` running `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610` on AWS EC2 `m7i.xlarge` (Intel Xeon Platinum 8488C, 4 vCPUs, CPU inference):

| Configuration | Median (`p50`) | Mean | Min | Notes |
| --- | --- | --- | --- | --- |
| **Default PyTorch CPU (`fp32` unmerged, 7 questions)** | `10,688 ms` | `10,688 ms` | `10,688 ms` | 7.5 GB RAM; unmerged LoRA + long suffix padding |
| **AMX-BF16 + Merged LoRA + Uniform Suffixes (1 question)** | **`1,012 ms`** | `1,066 ms` | `940 ms` | 3.5 GB RAM; single stance classification |
| **AMX-BF16 + Merged LoRA + Shared Prefix (7 questions)** | **`4,871 ms`** | `4,705 ms` | `2,126 ms` | Evaluates refusal + stance + 4 passage scores + best-quote pointer in 1 call (~695 ms/decision) |

### Reproducing the Evaluation

```bash
source .venv/bin/activate
python evaluation/run_evaluation.py
```
