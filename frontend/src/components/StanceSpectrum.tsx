"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { Info, ShieldAlert, HelpCircle, Sparkles } from "lucide-react";
import { ComparedModelResult, TopicSpec } from "@/lib/types";
import { ModelLogo } from "./ModelLogo";

interface StanceSpectrumProps {
  topic: TopicSpec;
  models: ComparedModelResult[];
  activeModelSlot: string | null;
  onSelectModelEvidence: (slotId: string, passageId: string | null) => void;
}

export function StanceSpectrum({
  topic,
  models,
  activeModelSlot,
  onSelectModelEvidence,
}: StanceSpectrumProps) {
  const [showRubric, setShowRubric] = useState(false);

  const onSpectrumModels = models.filter(
    (m) => m.status === "available" && m.placement.on_spectrum && m.placement.spectrum_x !== null
  );
  const offSpectrumModels = models.filter(
    (m) => m.status !== "available" || !m.placement.on_spectrum
  );

  return (
    <section
      aria-label="Topic-specific stance spectrum"
      className="bg-[#F5EFE4] border border-[#DDD3C2] rounded-2xl p-5 sm:p-7 shadow-[0_2px_16px_rgba(20,20,19,0.04)]"
    >
      {/* Top editorial bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-4 mb-5 border-b border-[#E3DACB]">
        <div className="flex items-center gap-2.5">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono uppercase tracking-wider bg-[#141413] text-[#FAF6F0]">
            <Sparkles className="w-3 h-3 text-[#E05A47]" />
            Stance Spectrum
          </span>
          <span className="text-xs text-[#615D55] font-sans">
            Click any model marker or stance label to inspect the supporting passage
          </span>
        </div>

        <button
          type="button"
          onClick={() => setShowRubric((v) => !v)}
          className="inline-flex items-center gap-1.5 text-xs font-mono uppercase tracking-wider text-[#4A4843] hover:text-[#141413] transition-colors px-2.5 py-1 rounded-md border border-[#D8CEBE] bg-[#FAF6F0]"
        >
          <Info className="w-3.5 h-3.5 text-[#C83E2B]" />
          {showRubric ? "Hide stance definitions" : "Topic stance rubric"}
        </button>
      </div>

      {/* Expandable topic-specific stance definitions */}
      {showRubric && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6 p-4 rounded-xl bg-[#FAF6F0] border border-[#E2D9C8] text-xs">
          <div className="p-3 rounded-lg bg-[#EFF6FF]/60 border border-[#BFDBFE]">
            <div className="font-mono uppercase tracking-wider text-[10px] text-[#1D4ED8] font-semibold mb-1">
              Left Pole · {topic.left_option.label}
            </div>
            <p className="text-[#2D2C29] leading-relaxed">{topic.left_option.description}</p>
          </div>
          <div className="p-3 rounded-lg bg-[#FEF3C7]/50 border border-[#FDE68A]">
            <div className="font-mono uppercase tracking-wider text-[10px] text-[#B45309] font-semibold mb-1">
              Middle Zone · {topic.center_option.label}
            </div>
            <p className="text-[#2D2C29] leading-relaxed">{topic.center_option.description}</p>
          </div>
          <div className="p-3 rounded-lg bg-[#F0FDFA]/70 border border-[#99F6E4]">
            <div className="font-mono uppercase tracking-wider text-[10px] text-[#0F766E] font-semibold mb-1">
              Right Pole · {topic.right_option.label}
            </div>
            <p className="text-[#2D2C29] leading-relaxed">{topic.right_option.description}</p>
          </div>
        </div>
      )}

      {/* Pole headers above the spectrum */}
      <div className="grid grid-cols-3 gap-2 mb-3 items-end">
        <div className="text-left">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#1D4ED8] font-semibold">
            Pole A
          </div>
          <div className="font-serif text-sm sm:text-base font-bold text-[#141413] leading-snug">
            {topic.left_option.label}
          </div>
        </div>

        <div className="text-center">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#B45309] font-semibold">
            Middle / Conditional
          </div>
          <div className="font-serif text-sm sm:text-base font-bold text-[#141413] leading-snug">
            {topic.center_option.label}
          </div>
        </div>

        <div className="text-right">
          <div className="text-[10px] font-mono uppercase tracking-widest text-[#0F766E] font-semibold">
            Pole B
          </div>
          <div className="font-serif text-sm sm:text-base font-bold text-[#141413] leading-snug">
            {topic.right_option.label}
          </div>
        </div>
      </div>

      {/* Horizontal Stance Track with 3 distinct non-judgmental editorial zones */}
      <div className="relative pt-12 pb-8">
        {/* Track bar */}
        <div className="relative h-4 rounded-full overflow-hidden border border-[#CFC4B1] bg-[#FAF6F0] grid grid-cols-3 shadow-inner">
          <div className="bg-gradient-to-r from-[#DBEAFE] via-[#EFF6FF] to-[#F5EFE4] border-r border-dashed border-[#C7B299]" />
          <div className="bg-gradient-to-r from-[#FEF3C7]/60 via-[#FDE68A]/70 to-[#FEF3C7]/60 border-r border-dashed border-[#C7B299]" />
          <div className="bg-gradient-to-r from-[#F5EFE4] via-[#CCFBF1]/60 to-[#99F6E4]/80" />
        </div>

        {/* Center tick & zone boundary ticks */}
        <div className="absolute left-1/3 top-11 h-6 w-px bg-[#B8AC99]" aria-hidden="true" />
        <div className="absolute left-1/2 top-10 h-8 w-0.5 bg-[#8C8273]/60" aria-hidden="true" />
        <div className="absolute left-2/3 top-11 h-6 w-px bg-[#B8AC99]" aria-hidden="true" />

        {/* Animated model tokens along the spectrum */}
        {onSpectrumModels.map((model, idx) => {
          const x = model.placement.spectrum_x ?? 50;
          const isSelected = activeModelSlot === model.slot_id;
          // Stagger vertical offset slightly if two markers are close
          const verticalStagger = idx % 2 === 1 ? "top-0" : "top-1";

          return (
            <motion.button
              key={model.slot_id}
              layout
              initial={{ opacity: 0, scale: 0.85, left: `${x}%` }}
              animate={{ opacity: 1, scale: isSelected ? 1.08 : 1, left: `${x}%` }}
              transition={{ type: "spring", stiffness: 240, damping: 26 }}
              onClick={() =>
                onSelectModelEvidence(model.slot_id, model.primary_evidence_passage_id)
              }
              style={{ left: `${x}%` }}
              className={`group absolute ${verticalStagger} -translate-x-1/2 flex flex-col items-center focus:outline-none z-10`}
              title={`${model.display_name}: ${model.placement.stance_label} (Click to inspect evidence passage)`}
            >
              {/* Pill with logo + short model name */}
              <div
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border shadow-md transition-all cursor-pointer ${
                  isSelected
                    ? "bg-[#141413] text-[#FAF6F0] border-[#141413] ring-2 ring-[#C83E2B]/50"
                    : "bg-[#FAF6F0] text-[#141413] border-[#C7B9A5] hover:border-[#141413]"
                }`}
              >
                <ModelLogo family={model.family} size="sm" />
                <span className="text-xs font-semibold tracking-tight pr-0.5 whitespace-nowrap">
                  {model.short_name}
                </span>
              </div>
              {/* Stem connecting token to spectrum bar */}
              <div
                className={`w-0.5 h-4 transition-colors ${
                  isSelected ? "bg-[#C83E2B]" : "bg-[#141413]/70 group-hover:bg-[#C83E2B]"
                }`}
              />
              <div
                className={`w-2.5 h-2.5 rounded-full border-2 border-[#FAF6F0] shadow-sm -mt-0.5 ${
                  isSelected ? "bg-[#C83E2B]" : "bg-[#141413]"
                }`}
              />
            </motion.button>
          );
        })}
      </div>

      {/* Separate tray for Refusal / Unclear / Unavailable (never forced onto stance axis) */}
      {offSpectrumModels.length > 0 && (
        <div className="mt-2 pt-4 border-t border-[#E2D9C8] flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-[#5A564E]">
            <span>Off-Spectrum Classifications (Not forced onto stance axis):</span>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            {offSpectrumModels.map((m) => {
              const isRefusal = m.placement.bucket === "refusal";
              const isUnclear = m.placement.bucket === "unclear";
              return (
                <button
                  key={m.slot_id}
                  type="button"
                  onClick={() =>
                    onSelectModelEvidence(m.slot_id, m.primary_evidence_passage_id)
                  }
                  className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[#D4C9B8] bg-[#FAF6F0] hover:border-[#141413] text-xs transition-all"
                >
                  <ModelLogo family={m.family} size="sm" />
                  <span className="font-semibold text-[#141413]">{m.display_name}:</span>
                  {isRefusal ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-rose-100 text-rose-900 font-mono text-[11px]">
                      <ShieldAlert className="w-3 h-3" /> Refusal
                    </span>
                  ) : isUnclear ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-stone-200 text-stone-800 font-mono text-[11px]">
                      <HelpCircle className="w-3 h-3" /> Unclear (Low Confidence)
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-stone-200 text-stone-700 font-mono text-[11px]">
                      Unavailable
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Explicit non-permanence editorial note required by spec */}
      <div className="mt-3 pt-3 border-t border-[#E5DEC9] flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px] text-[#6B665E]">
        <p className="italic">
          Note: These labels describe these particular responses; they do not claim to reveal permanent model beliefs.
        </p>
        <p className="font-mono text-[10px] uppercase tracking-wider text-[#7A746B]">
          Classified by Strands Decider 2B · Calibrated threshold ≥ 0.25
        </p>
      </div>
    </section>
  );
}
