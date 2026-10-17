"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Quote,
  Sparkles,
  ShieldAlert,
  HelpCircle,
} from "lucide-react";
import { ComparedModelResult } from "@/lib/types";
import { ModelLogo } from "./ModelLogo";

interface ModelCardProps {
  model: ComparedModelResult;
  highlightedPassageId: string | null;
  forceExpand: boolean;
  onClickStanceBadge: (slotId: string, passageId: string | null) => void;
}

export function ModelCard({
  model,
  highlightedPassageId,
  forceExpand,
  onClickStanceBadge,
}: ModelCardProps) {
  const [expanded, setExpanded] = useState(false);
  const passageRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    if (forceExpand) {
      setExpanded(true);
    }
  }, [forceExpand]);

  useEffect(() => {
    if (expanded && highlightedPassageId && passageRefs.current[highlightedPassageId]) {
      passageRefs.current[highlightedPassageId]?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }
  }, [expanded, highlightedPassageId]);

  const bucket = model.placement.bucket;

  const badgeStyle =
    bucket === "pole_a"
      ? "bg-[#EFF6FF] text-[#1D4ED8] border-[#BFDBFE] hover:bg-[#DBEAFE]"
      : bucket === "pole_b"
      ? "bg-[#F0FDFA] text-[#0F766E] border-[#99F6E4] hover:bg-[#CCFBF1]"
      : bucket === "mixed"
      ? "bg-[#FEF3C7] text-[#B45309] border-[#FDE68A] hover:bg-[#FDE68A]/70"
      : bucket === "refusal"
      ? "bg-rose-100 text-rose-900 border-rose-300"
      : "bg-stone-200 text-stone-800 border-stone-300";

  const handleStanceClick = () => {
    const targetPid =
      model.featured_quote?.passage_id ||
      model.primary_evidence_passage_id ||
      model.passages[0]?.id ||
      null;
    setExpanded(true);
    onClickStanceBadge(model.slot_id, targetPid);
  };

  return (
    <article
      id={`card-${model.slot_id}`}
      className="flex flex-col justify-between rounded-2xl bg-[#FAF6F0] border border-[#DDD3C2] shadow-[0_2px_12px_rgba(20,20,19,0.04)] hover:border-[#B8AC99] transition-all overflow-hidden"
    >
      <div className="p-5 sm:p-6">
        {/* 1. Model Name & Provider Header */}
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-center gap-3">
            <ModelLogo family={model.family} size="lg" />
            <div>
              <div className="text-[11px] font-mono uppercase tracking-widest text-[#706B62]">
                {model.provider}
              </div>
              <h3 className="font-serif text-lg sm:text-xl font-bold text-[#141413] leading-tight">
                {model.display_name}
              </h3>
            </div>
          </div>

          {model.decider && (
            <div
              className="text-right font-mono text-[11px] text-[#6B665E]"
              title="Strands Decider 2B calibrated stance confidence"
            >
              <div>conf {(model.decider.stance_confidence * 100).toFixed(0)}%</div>
              <div className="text-[10px] text-[#8C857B]">
                {model.decider.decider_latency_ms.toFixed(0)}ms
              </div>
            </div>
          )}
        </div>

        {/* 2. Topic-specific Stance Badge (clickable to reveal supporting passage) */}
        <div className="mb-4">
          <button
            type="button"
            onClick={handleStanceClick}
            className={`w-full text-left flex items-center justify-between gap-2 px-3.5 py-2 rounded-xl border text-xs font-medium transition-all cursor-pointer ${badgeStyle}`}
            title="Click to reveal the exact numbered passage supporting this stance"
          >
            <span className="flex items-center gap-1.5 font-semibold tracking-tight">
              {bucket === "refusal" && <ShieldAlert className="w-3.5 h-3.5 shrink-0" />}
              {bucket === "unclear" && <HelpCircle className="w-3.5 h-3.5 shrink-0" />}
              <span>{model.placement.stance_label}</span>
            </span>
            <span className="font-mono text-[10px] uppercase tracking-wider opacity-80 shrink-0">
              Inspect [{model.featured_quote?.passage_id || model.primary_evidence_passage_id || "P1"}] →
            </span>
          </button>
        </div>

        {/* 3. One sentence explaining its framing */}
        <div className="mb-4">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#78746C] mb-1">
            Distinctive Framing
          </div>
          <p className="text-sm text-[#1E1E1C] leading-relaxed font-sans">
            {model.framing_explanation}
          </p>
        </div>

        {/* 4. One exact, highlighted quotation verified against original */}
        {model.featured_quote && (
          <div
            onClick={handleStanceClick}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") handleStanceClick();
            }}
            className="group relative p-4 rounded-xl bg-[#F3ECE0] border-l-4 border-[#C83E2B] hover:bg-[#EFE5D4] transition-colors cursor-pointer"
          >
            <div className="flex items-center justify-between gap-2 mb-1.5">
              <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-[#C83E2B] font-semibold">
                <Quote className="w-3 h-3" />
                Supporting Evidence · Passage [{model.featured_quote.passage_id}]
              </span>
              {model.featured_quote.verified && (
                <span
                  className="inline-flex items-center gap-1 text-[10px] font-mono text-[#0F766E]"
                  title={`Verified exact substring (chars ${model.featured_quote.start_char}–${model.featured_quote.end_char})`}
                >
                  <CheckCircle2 className="w-3 h-3" />
                  Exact quote
                </span>
              )}
            </div>
            <blockquote className="font-serif text-sm text-[#141413] italic leading-relaxed">
              “{model.featured_quote.quote}”
            </blockquote>
          </div>
        )}
      </div>

      {/* 5. Expandable original answer with numbered passages & Decider relevance scores */}
      <div className="border-t border-[#E4DCCB] bg-[#F4EFE6]">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="w-full px-5 py-3 flex items-center justify-between text-xs font-mono uppercase tracking-wider text-[#4A4843] hover:text-[#141413] transition-colors"
        >
          <span>
            {expanded
              ? "Hide original response & passages"
              : `Read full response (${model.passages.length} passages)`}
          </span>
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {expanded && (
          <div className="px-5 pb-5 pt-2 space-y-2.5 border-t border-[#E6DEC8]">
            <div className="flex items-center justify-between text-[11px] font-mono text-[#6E6A61] mb-1">
              <span>Numbered passages scored by Strands Decider 2B</span>
              {model.decider && (
                <span>
                  {model.decider.selected_passage_ids.length}/{model.passages.length} selected for context
                </span>
              )}
            </div>

            {model.passages.map((p) => {
              const isHighlighted = highlightedPassageId === p.id;
              const isPrimary = p.id === model.primary_evidence_passage_id;
              const isSelected = p.selected_for_context;

              return (
                <div
                  key={p.id}
                  ref={(el) => {
                    passageRefs.current[p.id] = el;
                  }}
                  className={`p-3 rounded-xl border text-xs leading-relaxed transition-all ${
                    isHighlighted
                      ? "bg-[#FDF2F0] border-[#C83E2B] ring-2 ring-[#C83E2B]/30"
                      : isSelected
                      ? "bg-[#FAF6F0] border-[#C7B9A5]"
                      : "bg-[#EFEAE0]/60 border-[#E2D9C8] opacity-75"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-1.5 mb-1">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`px-1.5 py-0.5 rounded font-mono text-[10px] font-bold ${
                          isHighlighted || isPrimary
                            ? "bg-[#C83E2B] text-white"
                            : isSelected
                            ? "bg-[#141413] text-[#FAF6F0]"
                            : "bg-[#D8CEBE] text-[#4A4843]"
                        }`}
                      >
                        {p.id}
                      </span>
                      {isPrimary && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-mono text-[#C83E2B] font-semibold">
                          <Sparkles className="w-2.5 h-2.5" /> Primary stance evidence
                        </span>
                      )}
                      {!isPrimary && isSelected && (
                        <span className="text-[10px] font-mono text-[#0F766E]">
                          Selected for #context-memory
                        </span>
                      )}
                      {!isSelected && (
                        <span className="text-[10px] font-mono text-[#857F74]">
                          Pruned by Decider
                        </span>
                      )}
                    </div>

                    <span
                      className="font-mono text-[10px] text-[#5C5850]"
                      title="Strands Decider 2B passage relevance score (0.00 to 3.00 rubric)"
                    >
                      rel {p.relevance_score.toFixed(2)}/3.0
                    </span>
                  </div>
                  <p className="text-[#181816] font-sans">{p.text}</p>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </article>
  );
}
