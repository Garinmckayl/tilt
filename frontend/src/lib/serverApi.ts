import { ComparisonResult, EvaluationSummary, TopicSpec } from "./types";

const BACKEND_BASE = process.env.TILT_BACKEND_URL || "http://127.0.0.1:8098";

export async function fetchTopicsAndComparisons(): Promise<{
  topics: TopicSpec[];
  comparisons_by_topic: Record<string, ComparisonResult>;
}> {
  const res = await fetch(`${BACKEND_BASE}/api/topics`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch topics: ${res.status}`);
  }
  return res.json();
}

export async function fetchComparisonById(id: string): Promise<ComparisonResult | null> {
  const res = await fetch(`${BACKEND_BASE}/api/comparisons/${encodeURIComponent(id)}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    return null;
  }
  return res.json();
}

export async function fetchEvaluationSummary(): Promise<EvaluationSummary | null> {
  try {
    const res = await fetch(`${BACKEND_BASE}/api/evaluation`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
