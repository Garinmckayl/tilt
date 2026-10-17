"use client";

import React, { useState, useEffect } from "react";
import {
  Share2,
  SlidersHorizontal,
  Sparkles,
  Check,
  RefreshCw,
  Clock,
  ArrowRight,
  Compass,
  Scale,
  AlertCircle,
  Play,
  X,
  Zap,
} from "lucide-react";
import {
  ComparisonResult,
  EvaluationSummary,
  TopicSpec,
} from "@/lib/types";
import { StanceSpectrum } from "./StanceSpectrum";
import { ModelCard } from "./ModelCard";
import { HowAnalyzedDrawer } from "./HowAnalyzedDrawer";

interface TiltComparisonExperienceProps {
  initialTopics: TopicSpec[];
  initialComparisonsByTopic: Record<string, ComparisonResult>;
  initialComparison: ComparisonResult;
  evaluation: EvaluationSummary | null;
}

const CATEGORIES = ["All", "Technology", "Culture", "Economics", "Politics"];

export function TiltComparisonExperience({
  initialTopics,
  initialComparisonsByTopic,
  initialComparison,
  evaluation,
}: TiltComparisonExperienceProps) {
  const [topics] = useState<TopicSpec[]>(initialTopics);
  const [comparisonsByTopic, setComparisonsByTopic] = useState<Record<string, ComparisonResult>>(
    initialComparisonsByTopic
  );
  const [currentComparison, setCurrentComparison] = useState<ComparisonResult>(initialComparison);
  const [selectedCategory, setSelectedCategory] = useState<string>("All");

  // Custom question form state
  const [showCustomForm, setShowCustomForm] = useState<boolean>(!initialComparison.topic.is_curated);
  const [customQuestion, setCustomQuestion] = useState<string>(
    !initialComparison.topic.is_curated ? initialComparison.question : ""
  );
  const [customPoleA, setCustomPoleA] = useState<string>("");
  const [customPoleB, setCustomPoleB] = useState<string>("");

  // Loading & step animation state
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [loadingStage, setLoadingStage] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Evidence inspection state
  const [activeModelSlot, setActiveModelSlot] = useState<string | null>(null);
  const [highlightedPassageBySlot, setHighlightedPassageBySlot] = useState<Record<string, string | null>>({});
  const [forceExpandSlot, setForceExpandSlot] = useState<string | null>(null);

  // Drawer & share toast state
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const [videoModalOpen, setVideoModalOpen] = useState<boolean>(false);
  const [copiedShare, setCopiedShare] = useState<boolean>(false);

  // Progress stage ticker during live comparison
  useEffect(() => {
    if (!isLoading) {
      setLoadingStage(0);
      return;
    }
    const t1 = setTimeout(() => setLoadingStage(1), 2200);
    const t2 = setTimeout(() => setLoadingStage(2), 6800);
    const t3 = setTimeout(() => setLoadingStage(3), 13500);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [isLoading]);

  const filteredTopics =
    selectedCategory === "All"
      ? topics
      : topics.filter((t) => t.category.toLowerCase() === selectedCategory.toLowerCase());

  const handleSelectCuratedTopic = async (topic: TopicSpec) => {
    setErrorMessage(null);
    setShowCustomForm(false);
    setActiveModelSlot(null);
    setForceExpandSlot(null);

    const preloaded = comparisonsByTopic[topic.id];
    if (preloaded) {
      setCurrentComparison(preloaded);
      window.history.replaceState(null, "", `/c/${preloaded.id}`);
      return;
    }

    await executeCompare({ topic_id: topic.id, force_live: false });
  };

  const executeCompare = async (payload: {
    topic_id?: string;
    question?: string;
    custom_pole_a?: string;
    custom_pole_b?: string;
    force_live?: boolean;
  }) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const resp = await fetch("/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `Request failed with status ${resp.status}`);
      }
      const data: ComparisonResult = await resp.json();
      setCurrentComparison(data);
      if (data.topic?.id && data.topic.is_curated) {
        setComparisonsByTopic((prev) => ({ ...prev, [data.topic.id]: data }));
      }
      window.history.replaceState(null, "", `/c/${data.id}`);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to run comparison.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleCustomSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customQuestion.trim() || customQuestion.trim().length < 8) {
      setErrorMessage("Please enter a complete question (at least 8 characters).");
      return;
    }
    await executeCompare({
      question: customQuestion.trim(),
      custom_pole_a: customPoleA.trim() || undefined,
      custom_pole_b: customPoleB.trim() || undefined,
      force_live: false,
    });
  };

  const handleSelectModelEvidence = (slotId: string, passageId: string | null) => {
    setActiveModelSlot(slotId);
    setForceExpandSlot(slotId);
    if (passageId) {
      setHighlightedPassageBySlot((prev) => ({ ...prev, [slotId]: passageId }));
    }
    const cardEl = document.getElementById(`card-${slotId}`);
    if (cardEl) {
      cardEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  };

  const handleShareComparison = async () => {
    const shareUrl = `${window.location.origin}/c/${currentComparison.id}`;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopiedShare(true);
      setTimeout(() => setCopiedShare(false), 2600);
    } catch {
      window.prompt("Copy permanent comparison link:", shareUrl);
    }
  };

  const agreementBadge =
    currentComparison.summary.agreement_level === "divergent"
      ? {
          label: "Divergent Framing",
          cls: "bg-[#FDF2F0] text-[#C83E2B] border-[#F5C2B8]",
        }
      : currentComparison.summary.agreement_level === "broad_agreement"
      ? {
          label: "Broad Agreement · Distinct Emphasis",
          cls: "bg-[#F0FDFA] text-[#0F766E] border-[#99F6E4]",
        }
      : {
          label: "Nuanced Split Across Models",
          cls: "bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]",
        };

  return (
    <div className="min-h-screen bg-[#FAF6F0] text-[#141413] flex flex-col">
      {/* Top Editorial Masthead */}
      <header className="border-b border-[#DED5C4] bg-[#FAF6F0]/95 sticky top-0 z-30 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3.5">
            <a href="/" className="flex items-center gap-2.5 group">
              <img
                src="/logo.svg"
                alt="TILT logo"
                className="w-8 h-8 rounded-lg shadow-xs"
              />
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-serif font-black text-xl tracking-tight text-[#141413]">
                    TILT
                  </span>
                  <span className="text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 rounded bg-[#EAE2D3] text-[#3B3935] font-semibold">
                    Ground News for AI
                  </span>
                </div>
              </div>
            </a>
            <span className="hidden md:inline-block text-xs text-[#5E5A52] border-l border-[#D5CBB8] pl-3.5 font-serif italic">
              “Same question. Different AI. See the slant.”
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setVideoModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#C83E2B] hover:bg-[#A32E1E] text-white text-xs font-mono uppercase tracking-wider font-semibold shadow-sm transition-colors cursor-pointer"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Watch Demo</span>
            </button>

            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#CFC4B1] bg-[#F3ECE0] hover:bg-[#EAE0CF] text-xs font-mono uppercase tracking-wider text-[#141413] transition-colors cursor-pointer"
            >
              <SlidersHorizontal className="w-3.5 h-3.5 text-[#C83E2B]" />
              <span>How this was analyzed</span>
            </button>

            <button
              type="button"
              onClick={handleShareComparison}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#141413] hover:bg-[#C83E2B] text-[#FAF6F0] text-xs font-mono uppercase tracking-wider transition-colors cursor-pointer"
            >
              {copiedShare ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-300" />
                  <span>Link Copied!</span>
                </>
              ) : (
                <>
                  <Share2 className="w-3.5 h-3.5" />
                  <span>Share this comparison</span>
                </>
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Main Editorial Front Page */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
        {/* Consumer Editorial Lead */}
        <section className="border-b border-[#DED5C4] pb-6">
          <p className="font-mono text-xs sm:text-sm tracking-wide text-[#C83E2B] font-bold mb-2">
            Before you let AI shape your opinion, see how other AIs answer.
          </p>
          <h1 className="font-serif text-2xl sm:text-3xl lg:text-4xl font-black text-[#141413] tracking-tight leading-tight max-w-4xl">
            Millions of people ask AI what to believe. But whose perspective are they getting?
          </h1>
          <p className="mt-2.5 text-sm sm:text-base text-[#3D3A35] max-w-3xl leading-relaxed">
            Ask a single chatbot about a war, your rights, religion, or a controversial policy, and you receive one confident answer without seeing its assumptions.{" "}
            <strong className="text-[#141413]">
              TILT asks leading AIs the same question and exposes their differences side by side, so you can see the framing before it shapes your judgment.
            </strong>
          </p>
        </section>

        {/* Active Comparison Header + Provenance Controls (Real comparison directly beneath lead) */}
        <section className="pt-1">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono uppercase tracking-wider bg-[#EAE2D3] text-[#141413] font-semibold">
                {currentComparison.topic.category}
              </span>
              <span
                className={`px-2.5 py-0.5 rounded-full text-[11px] font-mono border font-medium ${agreementBadge.cls}`}
              >
                {agreementBadge.label}
              </span>
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-[#F3ECE0] border border-[#D8CEBE] text-[#5A564E]">
                <Clock className="w-3 h-3" />
                {currentComparison.cached ? "Verified Cached Run" : "Fresh Live Run"} · ID:{" "}
                {currentComparison.id}
              </span>
            </div>

            <button
              type="button"
              disabled={isLoading}
              onClick={() =>
                executeCompare({
                  topic_id: currentComparison.topic.is_curated
                    ? currentComparison.topic.id
                    : undefined,
                  question: !currentComparison.topic.is_curated
                    ? currentComparison.question
                    : undefined,
                  force_live: true,
                })
              }
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg border border-[#D8CEBE] bg-[#FAF6F0] hover:border-[#141413] text-[11px] font-mono uppercase tracking-wider text-[#4A4843] hover:text-[#141413] transition-colors cursor-pointer disabled:opacity-50"
              title="Re-query all 3 Bedrock models and Strands Decider 2B live"
            >
              <RefreshCw className={`w-3 h-3 ${isLoading ? "animate-spin" : ""}`} />
              <span>Compare perspectives live</span>
            </button>
          </div>

          <h2 className="font-serif text-3xl sm:text-4xl lg:text-[42px] font-black text-[#141413] tracking-tight leading-[1.12] my-2">
            {currentComparison.question}
          </h2>
          <p className="text-sm sm:text-base text-[#4A4843] font-sans max-w-3xl">
            Three foundation models answered this exact question under identical inference settings (
            <code className="font-mono text-xs bg-[#F3ECE0] px-1.5 py-0.5 rounded">
              temperature={currentComparison.provenance.shared_inference_settings.temperature}
            </code>
            ). Click any stance label or model marker to inspect the exact supporting passage.
          </p>
        </section>

        {/* Signature Visual: Topic-Specific Horizontal Stance Spectrum */}
        <StanceSpectrum
          topic={currentComparison.topic}
          models={currentComparison.models}
          activeModelSlot={activeModelSlot}
          onSelectModelEvidence={handleSelectModelEvidence}
        />

        {/* Compact Summary: "Where they differ" */}
        <section
          aria-label="Where they differ"
          className="bg-[#FAF6F0] border-l-4 border-[#141413] pl-5 pr-5 py-4 rounded-r-2xl bg-gradient-to-r from-[#F3ECE0] to-[#FAF6F0] shadow-sm"
        >
          <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
            <div className="flex items-center gap-2">
              <Scale className="w-4 h-4 text-[#C83E2B]" />
              <h3 className="font-mono text-xs uppercase tracking-widest font-bold text-[#141413]">
                Where they differ
              </h3>
            </div>
            <span className="font-mono text-[11px] text-[#6B665E]">
              Grounded in selected passages (
              {currentComparison.provenance.context_selection_stats.total_chars_after}/
              {currentComparison.provenance.context_selection_stats.total_chars_before} chars kept)
            </span>
          </div>
          <p className="font-serif text-base sm:text-lg text-[#141413] leading-relaxed">
            {currentComparison.summary.where_they_differ}
          </p>
        </section>

        {/* Three Model Comparison Cards */}
        <section aria-label="Model perspective cards">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {currentComparison.models.map((m) => (
              <ModelCard
                key={m.slot_id}
                model={m}
                highlightedPassageId={highlightedPassageBySlot[m.slot_id] || null}
                forceExpand={forceExpandSlot === m.slot_id}
                onClickStanceBadge={handleSelectModelEvidence}
              />
            ))}
          </div>
        </section>

        {/* Topic Switcher & Custom Question Selector */}
        <section
          id="topic-selector-section"
          aria-label="Explore more questions or ask your own"
          className="bg-[#F3ECE0] border border-[#DDD3C2] rounded-2xl p-4 sm:p-5"
        >
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div className="flex items-center gap-2">
              <Compass className="w-4 h-4 text-[#C83E2B]" />
              <span className="font-mono text-xs uppercase tracking-wider font-bold text-[#141413]">
                Explore another question or ask your own
              </span>
              <span className="hidden sm:inline text-xs text-[#6B665E]">
                · Compare how each model frames policy, economics, technology, and culture
              </span>
            </div>

            {/* Category filter pills + Custom Question button */}
            <div className="flex flex-wrap items-center gap-1.5">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => {
                    setSelectedCategory(cat);
                    setShowCustomForm(false);
                  }}
                  className={`px-2.5 py-1 rounded-md text-[11px] font-mono uppercase tracking-wider transition-colors cursor-pointer ${
                    !showCustomForm && selectedCategory === cat
                      ? "bg-[#141413] text-[#FAF6F0]"
                      : "bg-[#FAF6F0] text-[#5A564E] border border-[#D8CEBE] hover:border-[#141413]"
                  }`}
                >
                  {cat}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setShowCustomForm((v) => !v)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-mono uppercase tracking-wider transition-colors cursor-pointer ${
                  showCustomForm
                    ? "bg-[#C83E2B] text-white"
                    : "bg-[#FAF6F0] text-[#C83E2B] border border-[#E5B8B0] hover:bg-[#FDF2F0]"
                }`}
              >
                + Ask Custom Question
              </button>
            </div>
          </div>

          {/* Curated Topic Chips */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
            {filteredTopics.map((t) => {
              const isSelected = !showCustomForm && currentComparison.topic.id === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => handleSelectCuratedTopic(t)}
                  className={`text-left p-3 rounded-xl border transition-all cursor-pointer flex flex-col justify-between ${
                    isSelected
                      ? "bg-[#141413] text-[#FAF6F0] border-[#141413] shadow-md"
                      : "bg-[#FAF6F0] text-[#141413] border-[#D8CEBE] hover:border-[#141413]"
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between gap-1 mb-1">
                      <span
                        className={`text-[10px] font-mono uppercase tracking-wider ${
                          isSelected ? "text-[#E05A47]" : "text-[#C83E2B]"
                        }`}
                      >
                        {t.category}
                      </span>
                      <span
                        className={`text-[10px] font-mono ${
                          isSelected ? "text-[#C7B9A5]" : "text-[#7A746B]"
                        }`}
                      >
                        {t.left_option.short_label} ↔ {t.right_option.short_label}
                      </span>
                    </div>
                    <div className="font-serif text-xs sm:text-sm font-bold leading-snug">
                      {t.question}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Custom Question Form with visible topic-specific stance definitions */}
          {showCustomForm && (
            <form
              onSubmit={handleCustomSubmit}
              className="mt-4 pt-4 border-t border-[#DED5C4] space-y-3"
            >
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
                <div className="lg:col-span-6">
                  <label className="block text-[11px] font-mono uppercase tracking-wider text-[#4A4843] mb-1">
                    Controversial or policy question
                  </label>
                  <input
                    type="text"
                    value={customQuestion}
                    onChange={(e) => setCustomQuestion(e.target.value)}
                    placeholder="e.g., Should college admissions eliminate standardized testing like the SAT?"
                    className="w-full px-3.5 py-2 rounded-xl bg-[#FAF6F0] border border-[#C7B9A5] text-sm text-[#141413] focus:outline-none focus:border-[#141413]"
                  />
                </div>
                <div className="lg:col-span-3">
                  <label className="block text-[11px] font-mono uppercase tracking-wider text-[#1D4ED8] mb-1">
                    Optional Left Pole Label
                  </label>
                  <input
                    type="text"
                    value={customPoleA}
                    onChange={(e) => setCustomPoleA(e.target.value)}
                    placeholder="Auto-derived if blank"
                    className="w-full px-3 py-2 rounded-xl bg-[#FAF6F0] border border-[#C7B9A5] text-xs text-[#141413] focus:outline-none focus:border-[#141413]"
                  />
                </div>
                <div className="lg:col-span-3">
                  <label className="block text-[11px] font-mono uppercase tracking-wider text-[#0F766E] mb-1">
                    Optional Right Pole Label
                  </label>
                  <input
                    type="text"
                    value={customPoleB}
                    onChange={(e) => setCustomPoleB(e.target.value)}
                    placeholder="Auto-derived if blank"
                    className="w-full px-3 py-2 rounded-xl bg-[#FAF6F0] border border-[#C7B9A5] text-xs text-[#141413] focus:outline-none focus:border-[#141413]"
                  />
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-[#5E5A52]">
                  If pole labels are left blank, TILT derives a neutral 3-stance topic rubric and displays it on the spectrum before Strands Decider 2B classifies each model response.
                </p>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#C83E2B] hover:bg-[#A32E1E] disabled:opacity-50 text-white font-mono text-xs uppercase tracking-wider font-bold shadow-sm transition-colors cursor-pointer"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>{isLoading ? "Comparing perspectives..." : "Compare perspectives"}</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </form>
          )}

          {errorMessage && (
            <div className="mt-3 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}
        </section>

        {/* Live Progress Stepper when running a fresh comparison */}
        {isLoading && (
          <div className="p-6 rounded-2xl bg-[#141413] text-[#FAF6F0] border border-[#33312E] shadow-lg">
            <div className="flex items-center justify-between gap-4 mb-4">
              <div className="flex items-center gap-2.5">
                <RefreshCw className="w-4 h-4 text-[#E05A47] animate-spin" />
                <span className="font-mono text-xs uppercase tracking-wider text-[#E05A47] font-semibold">
                  Live Pipeline Execution on AWS
                </span>
              </div>
              <span className="font-mono text-[11px] text-[#A39E93]">
                Strands Decider 2B + Amazon Bedrock
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs font-mono">
              {[
                "1. Querying Claude Sonnet 4.5, Llama 3.3 70B & DeepSeek V3.2 with identical prompts",
                "2. Splitting responses into numbered passages [P1..PN]",
                "3. Strands Decider 2B classifying stance & scoring passage relevance (#context-memory)",
                "4. Strands Agent synthesizing framing & verifying verbatim quotes",
              ].map((stepText, idx) => (
                <div
                  key={stepText}
                  className={`p-3 rounded-xl border ${
                    loadingStage >= idx
                      ? "bg-[#242320] border-[#E05A47] text-[#FAF6F0]"
                      : "bg-[#1B1A18] border-[#2E2C28] text-[#78746C]"
                  }`}
                >
                  {stepText}
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* Editorial Footer */}
      <footer className="border-t border-[#DED5C4] bg-[#F3ECE0] mt-12 py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-[#5A564E]">
          <div className="flex items-center gap-2">
            <span className="font-serif font-bold text-[#141413]">
              TILT: Ground News for AI
            </span>
            <span>·</span>
            <span>“Same question. Different AI. See the slant.”</span>
          </div>
          <div className="flex flex-wrap items-center gap-2 font-mono text-[11px]">
            <span className="px-2 py-0.5 rounded bg-[#FAF6F0] border border-[#D8CEBE] text-[#141413]">
              #strands-decider-2b
            </span>
            <span className="px-2 py-0.5 rounded bg-[#FAF6F0] border border-[#D8CEBE] text-[#C83E2B]">
              #context-memory
            </span>
            <span>·</span>
            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              className="underline hover:text-[#141413] cursor-pointer"
            >
              How this was analyzed
            </button>
          </div>
        </div>
      </footer>

      {/* Optional "How this was analyzed" Drawer */}
      <HowAnalyzedDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        comparison={currentComparison}
        evaluation={evaluation}
      />

      {/* Narrated Demo Modal */}
      {videoModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
          onClick={() => setVideoModalOpen(false)}
        >
          <div
            className="relative w-full max-w-5xl rounded-2xl bg-[#141413] border border-[#383530] shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#2C2A27]">
              <div className="flex items-center gap-2.5">
                <span className="px-2 py-0.5 rounded bg-[#C83E2B] text-white font-mono text-[10px] uppercase tracking-widest font-bold">
                  Product Walkthrough
                </span>
                <span className="font-serif font-bold text-sm sm:text-base text-[#FAF6F0]">
                  TILT: Ground News for AI (“Same question. Different AI. See the slant.”)
                </span>
              </div>
              <button
                type="button"
                onClick={() => setVideoModalOpen(false)}
                className="p-1.5 rounded-lg text-[#A39E93] hover:text-white hover:bg-[#2C2A27] transition-colors cursor-pointer"
                aria-label="Close video modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="bg-black aspect-video w-full">
              <video
                src="/demo.mp4"
                controls
                autoPlay
                playsInline
                className="w-full h-full object-contain"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
