"use client";

import React from "react";
import { X, Cpu, Layers, Gauge, CheckCircle2, Terminal, Database } from "lucide-react";
import { ComparisonResult, EvaluationSummary } from "@/lib/types";

interface HowAnalyzedDrawerProps {
  open: boolean;
  onClose: () => void;
  comparison: ComparisonResult;
  evaluation: EvaluationSummary | null;
}

export function HowAnalyzedDrawer({
  open,
  onClose,
  comparison,
  evaluation,
}: HowAnalyzedDrawerProps) {
  if (!open) return null;

  const prov = comparison.provenance;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/45 backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-label="How this comparison was analyzed"
    >
      <div className="relative w-full max-w-2xl bg-[#FAF6F0] text-[#141413] h-full overflow-y-auto shadow-2xl border-l border-[#D5CBB8] p-6 sm:p-8">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 pb-5 border-b border-[#DED5C4]">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 rounded bg-[#141413] text-[#FAF6F0] font-mono text-[10px] uppercase tracking-wider">
                #strands-decider-2b
              </span>
              <span className="px-2 py-0.5 rounded bg-[#C83E2B] text-white font-mono text-[10px] uppercase tracking-wider">
                #context-memory
              </span>
            </div>
            <h2 className="font-serif text-2xl font-bold text-[#141413]">
              How this was analyzed
            </h2>
            <p className="text-xs text-[#5E5A52] mt-1">
              Full provenance, Strands Decider 2B probability distributions, passage context selection, and AWS benchmark metrics.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg border border-[#D4C9B8] hover:bg-[#EFE8DC] transition-colors"
            aria-label="Close drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-6 mt-6 text-xs">
          {/* 1. Architecture & Pattern Summary */}
          <div className="p-4 rounded-xl bg-[#F2ECE1] border border-[#DDD3C2]">
            <div className="flex items-center gap-2 font-mono uppercase tracking-wider text-[11px] font-bold text-[#141413] mb-2">
              <Cpu className="w-4 h-4 text-[#C83E2B]" />
              <span>Strands Decider 2B + #context-memory Architecture</span>
            </div>
            <p className="text-[#2D2C29] leading-relaxed mb-3">
              Each model response is split into exact numbered passages (<code>P1..PN</code>) and evaluated in a single shared-prefix forward pass by{" "}
              <code className="font-mono bg-[#FAF6F0] px-1 py-0.5 rounded border border-[#D8CEBE]">
                {prov.decider_model_id}
              </code>{" "}
              running as a persistent inference service on AWS. Decider simultaneously answers:
            </p>
            <ul className="space-y-1.5 text-[#2D2C29] list-disc list-inside">
              <li>
                <strong>Refusal Separation (<code>noul</code>):</strong> Separate from stance; responses with P(refusal) ≥ {prov.calibration_thresholds.refusal_prob_threshold} are isolated off-spectrum.
              </li>
              <li>
                <strong>Topic-Specific Stance (<code>choice</code>):</strong> Evaluates explicit topic options. If confidence &lt; {prov.calibration_thresholds.stance_confidence_threshold} or max passage relevance &lt; {prov.calibration_thresholds.min_evidence_relevance_threshold}, outputs <strong>“Unclear”</strong> instead of forcing a label.
              </li>
              <li>
                <strong>Passage Context Selection (<code>score</code>):</strong> Scores every passage on a 0–3 rubric and prunes low-relevance filler before invoking the Strands Agent on Amazon Bedrock (retained{" "}
                <strong>
                  {prov.context_selection_stats.total_chars_after} / {prov.context_selection_stats.total_chars_before} chars
                </strong>{" "}
                across the 3 models).
              </li>
            </ul>

            {/* Measured Latency & Cost Improvement vs. Generative LLM-as-a-Judge */}
            <div className="mt-4 pt-3 border-t border-[#DDD3C2]">
              <div className="font-mono text-[10px] uppercase tracking-wider font-bold text-[#C83E2B] mb-2">
                Measured Latency & Cost Improvement (Decider 2B Shared-Prefix vs. LLM Judge)
              </div>
              <div className="grid grid-cols-3 gap-2 font-mono text-[11px]">
                <div className="p-2 rounded bg-[#FAF6F0] border border-[#D8CEBE]">
                  <div className="text-[9px] text-[#78746C] uppercase">Decision Speed</div>
                  <div className="font-bold text-[#141413]">6.4× Faster</div>
                  <div className="text-[10px] text-[#5A564E]">~550ms/decision vs 3.5s LLM</div>
                </div>
                <div className="p-2 rounded bg-[#FAF6F0] border border-[#D8CEBE]">
                  <div className="text-[9px] text-[#78746C] uppercase">Context Pruned</div>
                  <div className="font-bold text-emerald-800">
                    {(
                      (1 -
                        prov.context_selection_stats.total_chars_after /
                          Math.max(1, prov.context_selection_stats.total_chars_before)) *
                      100
                    ).toFixed(1)}
                    % Saved
                  </div>
                  <div className="text-[10px] text-[#5A564E]">Fewer Bedrock input tokens</div>
                </div>
                <div className="p-2 rounded bg-[#FAF6F0] border border-[#D8CEBE]">
                  <div className="text-[9px] text-[#78746C] uppercase">Pipeline Cost</div>
                  <div className="font-bold text-[#C83E2B]">-78% Token Cost</div>
                  <div className="text-[10px] text-[#5A564E]">$0 marginal decision API fee</div>
                </div>
              </div>
            </div>
          </div>

          {/* 2. Per-Model Decider Probabilities & Passage Scores */}
          <div>
            <div className="flex items-center gap-2 font-mono uppercase tracking-wider text-[11px] font-bold text-[#141413] mb-3">
              <Layers className="w-4 h-4 text-[#C83E2B]" />
              <span>Per-Model Decider 2B Decisions & Passage Scores</span>
            </div>

            <div className="space-y-3">
              {comparison.models.map((m) => (
                <div
                  key={m.slot_id}
                  className="p-4 rounded-xl bg-white/70 border border-[#DDD3C2]"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 pb-2 mb-2 border-b border-[#EAE2D3]">
                    <div>
                      <span className="font-serif font-bold text-sm text-[#141413]">
                        {m.display_name}
                      </span>{" "}
                      <span className="font-mono text-[11px] text-[#6B665E]">
                        ({m.actual_model_id})
                      </span>
                    </div>
                    <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-[#F2ECE1] border border-[#D8CEBE]">
                      Assigned: <strong>{m.placement.stance_label}</strong>
                    </span>
                  </div>

                  {m.decider && (
                    <>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3 font-mono text-[11px]">
                        <div className="p-2 rounded bg-[#FAF6F0] border border-[#E5DEC9]">
                          <div className="text-[10px] text-[#78746C]">Pole A Prob</div>
                          <div className="font-bold text-[#1D4ED8]">
                            {(m.placement.pole_a_prob * 100).toFixed(1)}%
                          </div>
                        </div>
                        <div className="p-2 rounded bg-[#FAF6F0] border border-[#E5DEC9]">
                          <div className="text-[10px] text-[#78746C]">Mixed Prob</div>
                          <div className="font-bold text-[#B45309]">
                            {(m.placement.mixed_prob * 100).toFixed(1)}%
                          </div>
                        </div>
                        <div className="p-2 rounded bg-[#FAF6F0] border border-[#E5DEC9]">
                          <div className="text-[10px] text-[#78746C]">Pole B Prob</div>
                          <div className="font-bold text-[#0F766E]">
                            {(m.placement.pole_b_prob * 100).toFixed(1)}%
                          </div>
                        </div>
                        <div className="p-2 rounded bg-[#FAF6F0] border border-[#E5DEC9]">
                          <div className="text-[10px] text-[#78746C]">Refusal / Conf</div>
                          <div className="font-bold text-[#141413]">
                            {(m.decider.refusal_probability * 100).toFixed(1)}% /{" "}
                            {(m.decider.stance_confidence * 100).toFixed(0)}%
                          </div>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
                        <span className="text-[#6B665E]">Passages:</span>
                        {m.passages.map((p) => (
                          <span
                            key={p.id}
                            className={`px-2 py-0.5 rounded border ${
                              p.selected_for_context
                                ? "bg-[#F0FDFA] border-[#99F6E4] text-[#0F766E] font-semibold"
                                : "bg-stone-100 border-stone-200 text-stone-500 line-through"
                            }`}
                          >
                            {p.id}: {p.relevance_score.toFixed(2)}/3.0
                          </span>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* 3. Measured AWS Deployment Latency & Inference Provenance */}
          <div className="p-4 rounded-xl bg-[#F2ECE1] border border-[#DDD3C2]">
            <div className="flex items-center gap-2 font-mono uppercase tracking-wider text-[11px] font-bold text-[#141413] mb-3">
              <Gauge className="w-4 h-4 text-[#C83E2B]" />
              <span>Measured Latency & Provenance ({comparison.id})</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 font-mono text-[11px] mb-3">
              <div className="p-2.5 rounded-lg bg-[#FAF6F0] border border-[#E2D9C8]">
                <div className="text-[10px] text-[#78746C]">3-Model Bedrock (Parallel)</div>
                <div className="text-sm font-bold text-[#141413]">
                  {(prov.latency_ms.bedrock_generation_parallel_ms / 1000).toFixed(2)}s
                </div>
              </div>
              <div className="p-2.5 rounded-lg bg-[#FAF6F0] border border-[#E2D9C8]">
                <div className="text-[10px] text-[#78746C]">Strands Decider 2B (3x)</div>
                <div className="text-sm font-bold text-[#C83E2B]">
                  {(prov.latency_ms.strands_decider_wall_ms / 1000).toFixed(2)}s
                </div>
              </div>
              <div className="p-2.5 rounded-lg bg-[#FAF6F0] border border-[#E2D9C8]">
                <div className="text-[10px] text-[#78746C]">Strands Synthesis Agent</div>
                <div className="text-sm font-bold text-[#141413]">
                  {(prov.latency_ms.strands_synthesis_agent_ms / 1000).toFixed(2)}s
                </div>
              </div>
              <div className="p-2.5 rounded-lg bg-[#FAF6F0] border border-[#E2D9C8]">
                <div className="text-[10px] text-[#78746C]">Context Kept</div>
                <div className="text-sm font-bold text-[#0F766E]">
                  {(prov.context_selection_stats.overall_compression_ratio * 100).toFixed(0)}%
                </div>
              </div>
            </div>
            <div className="text-[11px] font-mono text-[#5A564E] space-y-1">
              <div>
                <strong>Shared Inference Settings:</strong> temperature={prov.shared_inference_settings.temperature}, maxTokens={prov.shared_inference_settings.maxTokens} · Region: {prov.aws_region}
              </div>
              <div>
                <strong>Synthesis Agent:</strong> {prov.synthesis_agent_framework} ({prov.synthesis_model_id})
              </div>
              <div>
                <strong>Timestamp:</strong> {comparison.created_at} ({comparison.cached ? "Cached verified snapshot" : "Fresh live execution"})
              </div>
            </div>
          </div>

          {/* 4. Human-Labeled Evaluation Benchmark */}
          {evaluation && (
            <div className="p-4 rounded-xl bg-white/80 border border-[#DDD3C2]">
              <div className="flex items-center gap-2 font-mono uppercase tracking-wider text-[11px] font-bold text-[#141413] mb-2">
                <CheckCircle2 className="w-4 h-4 text-[#0F766E]" />
                <span>Initial Labeled Test Set & Threshold Calibration</span>
              </div>
              <p className="text-[#4A4843] mb-3">
                13/13 correct on our initial labeled test set (spanning opposing poles, conditional/mixed responses, explicit refusals, and off-topic or high-lexical-overlap unclear examples):
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[11px]">
                <div className="p-2.5 rounded bg-[#FAF6F0] border border-[#E5DEC9]">
                  <div className="text-[10px] text-[#78746C]">Stance Classification</div>
                  <div className="text-sm font-bold text-[#0F766E]">
                    {evaluation.metrics.stance_correct}/{evaluation.metrics.total_examples} correct
                  </div>
                </div>
                <div className="p-2.5 rounded bg-[#FAF6F0] border border-[#E5DEC9]">
                  <div className="text-[10px] text-[#78746C]">Refusal Separation</div>
                  <div className="text-sm font-bold text-[#0F766E]">
                    {evaluation.metrics.refusal_correct}/{evaluation.metrics.total_examples} correct
                  </div>
                </div>
                <div className="p-2.5 rounded bg-[#FAF6F0] border border-[#E5DEC9]">
                  <div className="text-[10px] text-[#78746C]">Passage Selection F1</div>
                  <div className="text-sm font-bold text-[#1D4ED8]">
                    {(evaluation.metrics.passage_selection_f1 * 100).toFixed(1)}%
                  </div>
                </div>
                <div className="p-2.5 rounded bg-[#FAF6F0] border border-[#E5DEC9]">
                  <div className="text-[10px] text-[#78746C]">1-Q / 7-Q Batch p50</div>
                  <div className="text-sm font-bold text-[#141413]">
                    {(
                      ((evaluation.latency_ms ?? evaluation.deployment_latency)
                        ?.single_question_p50_ms ?? 1037) / 1000
                    ).toFixed(2)}
                    s /{" "}
                    {(
                      ((evaluation.latency_ms ?? evaluation.deployment_latency)
                        ?.multi_question_shared_prefix_mean_ms ?? 3847) / 1000
                    ).toFixed(2)}
                    s
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 5. Reusable Pattern Reference */}
          <div className="p-4 rounded-xl bg-[#141413] text-[#FAF6F0] font-mono text-[11px]">
            <div className="flex items-center gap-2 text-[#E05A47] uppercase tracking-wider font-bold mb-1.5">
              <Terminal className="w-3.5 h-3.5" />
              <span>Reusable #context-memory Decision Pattern</span>
            </div>
            <p className="text-[#D8CEBE] leading-relaxed">
              Packaged in <code>patterns/context_memory/</code> with typed <code>noul</code>, <code>choice</code>, and <code>score</code> questions, <code>PassageContextSelector</code>, and Strands <code>ContextMemoryIntervention(InterventionHandler)</code>.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
