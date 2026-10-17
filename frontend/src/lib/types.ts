export interface StanceOption {
  key: string;
  label: string;
  short_label: string;
  description: string;
  pole: "left" | "center" | "right";
}

export interface TopicSpec {
  id: string;
  question: string;
  short_title: string;
  category: "Technology" | "Culture" | "Economics" | "Politics" | "Custom" | string;
  is_curated: boolean;
  left_option: StanceOption;
  center_option: StanceOption;
  right_option: StanceOption;
  stance_criteria: Record<string, string>;
  comparison_id?: string;
  created_at?: string;
  summary?: ComparisonSummary;
  preview_placements?: Array<{
    slot_id: string;
    display_name: string;
    short_name: string;
    family: string;
    accent_color: string;
    bucket: string;
    stance_label: string;
    stance_short_label: string;
    on_spectrum: boolean;
    spectrum_x: number | null;
  }>;
}

export interface PassageScore {
  id: string;
  number: number;
  text: string;
  start_char: number;
  end_char: number;
  relevance_score: number;
  relevance_normalized: number;
  relevance_confidence: number;
  level_probabilities: Record<string, number>;
  evidence_choice_probability: number;
  combined_utility: number;
  selected_for_context: boolean;
  is_primary_evidence: boolean;
}

export interface FeaturedQuote {
  verified: boolean;
  source: string;
  quote: string;
  start_char: number;
  end_char: number;
  passage_id: string;
}

export interface ModelPlacement {
  bucket: "pole_a" | "mixed" | "pole_b" | "refusal" | "unclear" | "unavailable";
  stance_key: string;
  stance_label: string;
  stance_short_label: string;
  stance_description: string;
  on_spectrum: boolean;
  spectrum_x: number | null;
  pole_a_prob: number;
  mixed_prob: number;
  pole_b_prob: number;
}

export interface ModelDeciderDetails {
  assigned_stance: string;
  raw_top_stance: string;
  stance_probabilities: Record<string, number>;
  stance_confidence: number;
  is_refusal: boolean;
  refusal_probability: number;
  is_unclear: boolean;
  unclear_reason: string | null;
  selected_passage_ids: string[];
  pruned_passage_ids: string[];
  primary_evidence_passage_id: string;
  context_compression_ratio: number;
  context_reduction_ratio: number;
  total_char_count: number;
  selected_char_count: number;
  decider_latency_ms: number;
  decider_usage: {
    input_tokens: number;
    output_tokens: number;
  };
}

export interface ComparedModelResult {
  slot_id: string;
  display_name: string;
  short_name: string;
  provider: string;
  family: "claude" | "llama" | "deepseek" | string;
  requested_model_id: string;
  actual_model_id: string;
  used_fallback: boolean;
  status: "available" | "unavailable";
  error: string | null;
  original_response: string;
  generation_latency_ms: number;
  usage: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
  accent_color: string;
  badge_bg: string;
  placement: ModelPlacement;
  decider: ModelDeciderDetails | null;
  passages: PassageScore[];
  selected_passage_ids: string[];
  primary_evidence_passage_id: string | null;
  framing_explanation: string;
  featured_quote: FeaturedQuote | null;
}

export interface ComparisonSummary {
  where_they_differ: string;
  headline_summary: string;
  agreement_level: "divergent" | "nuanced_split" | "broad_agreement" | string;
  unique_stance_count: number;
}

export interface ComparisonProvenance {
  decider_model_id: string;
  decider_service_url: string;
  pattern_tags: string[];
  synthesis_agent_framework: string;
  synthesis_model_id: string;
  aws_region: string;
  shared_prompt_template: string;
  shared_inference_settings: {
    temperature: number;
    maxTokens: number;
  };
  calibration_thresholds: {
    refusal_prob_threshold: number;
    stance_confidence_threshold: number;
    min_evidence_relevance_threshold: number;
    mixed_margin_threshold: number;
    passage_relevance_threshold: number;
    max_selected_passages: number;
    min_selected_passages: number;
  };
  context_selection_stats: {
    total_chars_before: number;
    total_chars_after: number;
    overall_compression_ratio: number;
  };
  latency_ms: {
    bedrock_generation_parallel_ms: number;
    strands_decider_total_ms: number;
    strands_decider_wall_ms: number;
    strands_synthesis_agent_ms: number;
    total_pipeline_wall_ms: number;
  };
}

export interface ComparisonResult {
  id: string;
  created_at: string;
  cached: boolean;
  topic: TopicSpec;
  question: string;
  summary: ComparisonSummary;
  models: ComparedModelResult[];
  provenance: ComparisonProvenance;
}

export interface EvaluationSummary {
  decider_model: string;
  pattern_tags: string[];
  calibrated_thresholds: Record<string, number>;
  metrics: {
    total_examples: number;
    stance_accuracy: number;
    stance_correct: number;
    refusal_accuracy: number;
    refusal_correct: number;
    passage_selection_precision: number;
    passage_selection_recall: number;
    passage_selection_f1: number;
    primary_evidence_hit_rate: number;
    mean_context_reduction_ratio: number;
  };
  latency_ms?: {
    single_question_p50_ms: number;
    single_question_mean_ms: number;
    multi_question_shared_prefix_p50_ms: number;
    multi_question_shared_prefix_mean_ms: number;
    questions_per_batch_avg: number;
  };
  deployment_latency?: {
    single_question_p50_ms: number;
    single_question_mean_ms: number;
    multi_question_shared_prefix_p50_ms: number;
    multi_question_shared_prefix_mean_ms: number;
    questions_per_batch_avg: number;
  };
}
