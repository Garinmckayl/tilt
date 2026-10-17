"""Run human-labeled evaluation and threshold calibration on Strands Decider 2B.

Tags: #strands-decider-2b #context-memory
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from patterns.context_memory import (
    CalibrationThresholds,
    DeciderClient,
    PassageContextSelector,
)


def evaluate_dataset() -> dict:
    dataset_path = os.path.join(os.path.dirname(__file__), "human_labeled_dataset.json")
    with open(dataset_path, encoding="utf-8") as f:
        items = json.load(f)

    decider = DeciderClient()
    health = decider.health()
    thresholds = CalibrationThresholds(
        refusal_prob_threshold=0.75,
        stance_confidence_threshold=0.35,
        mixed_margin_threshold=0.08,
        passage_relevance_threshold=1.50,
        max_selected_passages=2,
        min_selected_passages=1,
    )
    selector = PassageContextSelector(decider=decider, thresholds=thresholds)

    # Warm-up call
    _ = selector.evaluate_response(
        question_text=items[0]["topic"],
        response_text=items[0]["response_text"],
        stance_options=items[0]["stance_options"],
    )

    # Also measure single-question latency vs multi-question shared-prefix latency
    single_q_latencies: list[float] = []
    for item in items[:5]:
        raw_single = decider.ask_raw(
            f"Question: {item['topic']}\n\nResponse:\n{item['response_text']}",
            {"stance": DeciderClient.choice(f"Overall stance on '{item['topic']}'?", item["stance_options"])},
        )
        single_q_latencies.append(float(raw_single["latency_ms"]))

    case_results = []
    stance_correct = 0
    refusal_correct = 0
    primary_hit = 0
    tp = fp = fn = 0
    latencies: list[float] = []
    reduction_ratios: list[float] = []

    for item in items:
        decision = selector.evaluate_response(
            question_text=item["topic"],
            response_text=item["response_text"],
            stance_options=item["stance_options"],
        )
        latencies.append(decision.latency_ms)

        is_stance_match = decision.assigned_stance == item["gold_stance"]
        if is_stance_match:
            stance_correct += 1

        is_refusal_match = decision.is_refusal == item["gold_is_refusal"]
        if is_refusal_match:
            refusal_correct += 1

        gold_rel = set(item["gold_relevant_passages"])
        pred_rel = set(decision.selected_passage_ids)
        if not item["gold_is_refusal"] and item["gold_stance"] != "unclear":
            tp += len(gold_rel & pred_rel)
            fp += len(pred_rel - gold_rel)
            fn += len(gold_rel - pred_rel)
            reduction_ratios.append(decision.context_reduction_ratio)

        is_primary_match = (
            decision.primary_passage_id == item["gold_primary_passage"]
            or decision.primary_passage_id in gold_rel
        )
        if is_primary_match:
            primary_hit += 1

        case_results.append(
            {
                "id": item["id"],
                "topic": item["topic"],
                "gold_stance": item["gold_stance"],
                "predicted_stance": decision.assigned_stance,
                "raw_top_stance": decision.raw_top_stance,
                "stance_confidence": decision.stance_confidence,
                "stance_probabilities": decision.stance_probabilities,
                "stance_correct": is_stance_match,
                "gold_is_refusal": item["gold_is_refusal"],
                "predicted_is_refusal": decision.is_refusal,
                "refusal_probability": decision.refusal_probability,
                "refusal_correct": is_refusal_match,
                "gold_relevant_passages": item["gold_relevant_passages"],
                "selected_passage_ids": decision.selected_passage_ids,
                "primary_passage_id": decision.primary_passage_id,
                "primary_hit": is_primary_match,
                "context_reduction_ratio": decision.context_reduction_ratio,
                "passage_scores": {
                    p.id: {
                        "score": p.relevance_score,
                        "evidence_prob": p.evidence_choice_probability,
                        "utility": p.combined_utility,
                    }
                    for p in decision.passages
                },
                "latency_ms": decision.latency_ms,
                "input_tokens": decision.input_tokens,
            }
        )

    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)

    # Threshold sweep over recorded confidence, refusal, and evidence relevance
    threshold_sweep = []
    for conf_thresh in [0.10, 0.20, 0.25, 0.30, 0.35, 0.45, 0.55]:
        correct_stance_only = 0
        correct_joint = 0
        for r in case_results:
            max_rel = max(p["score"] for p in r["passage_scores"].values())
            if r["refusal_probability"] >= 0.75:
                pred_only = "refusal"
                pred_joint = "refusal"
            else:
                pred_only = "unclear" if r["stance_confidence"] < conf_thresh else r["raw_top_stance"]
                pred_joint = (
                    "unclear"
                    if (r["stance_confidence"] < conf_thresh or max_rel < 1.45)
                    else r["raw_top_stance"]
                )
            if pred_only == r["gold_stance"]:
                correct_stance_only += 1
            if pred_joint == r["gold_stance"]:
                correct_joint += 1
        threshold_sweep.append(
            {
                "stance_confidence_threshold": conf_thresh,
                "stance_only_accuracy": round(correct_stance_only / len(case_results), 4),
                "joint_evidence_gated_accuracy": round(correct_joint / len(case_results), 4),
                "correct_joint": correct_joint,
                "total": len(case_results),
            }
        )

    summary = {
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "decider_health": health,
        "thresholds": thresholds.__dict__,
        "metrics": {
            "total_examples": len(items),
            "stance_accuracy": round(stance_correct / len(items), 4),
            "stance_correct": stance_correct,
            "refusal_accuracy": round(refusal_correct / len(items), 4),
            "refusal_correct": refusal_correct,
            "passage_selection_precision": round(precision, 4),
            "passage_selection_recall": round(recall, 4),
            "passage_selection_f1": round(f1, 4),
            "primary_evidence_hit_rate": round(primary_hit / len(items), 4),
            "mean_context_reduction_ratio": round(statistics.mean(reduction_ratios), 4),
        },
        "latency_ms": {
            "single_question_p50_ms": round(statistics.median(single_q_latencies), 2),
            "single_question_mean_ms": round(statistics.mean(single_q_latencies), 2),
            "multi_question_shared_prefix_p50_ms": round(statistics.median(latencies), 2),
            "multi_question_shared_prefix_mean_ms": round(statistics.mean(latencies), 2),
            "multi_question_shared_prefix_min_ms": round(min(latencies), 2),
            "multi_question_shared_prefix_max_ms": round(max(latencies), 2),
            "questions_per_batch_avg": 7,
        },
        "threshold_sweep": threshold_sweep,
        "cases": case_results,
    }

    out_path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


if __name__ == "__main__":
    res = evaluate_dataset()
    print(json.dumps(res["metrics"], indent=2))
    print(json.dumps(res["latency_ms"], indent=2))
    print("Threshold sweep:", json.dumps(res["threshold_sweep"], indent=2))
    for c in res["cases"]:
        print(
            f"  {c['id']:30s} | gold={c['gold_stance']:17s} pred={c['predicted_stance']:17s} "
            f"(conf={c['stance_confidence']:.3f}, ref={c['refusal_probability']:.3f}) "
            f"| sel={c['selected_passage_ids']} (gold={c['gold_relevant_passages']})"
        )
